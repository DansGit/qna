import os
import codecs
import json
import tempfile
import string
from nltk import Tree
import parsedatetime.parsedatetime as pdt
import corenlp
import database
from progressbar import ProgressBar
from triplet_extraction import extract_triplet

# Set up a place to store temp files and log.
DATA = tempfile.mkdtemp()
TEMP = os.path.join(DATA, 'temp')
os.mkdir(TEMP)

def monitor_progress(num_files):
    """Watches a log file changes and draws a progress bar
    in the terminal.
    """
    from time import sleep
    import sys

    pbar = ProgressBar(num_files)

    # Try three times to open the file
    for x in range(3):
        try:
            f = open(os.path.join(DATA, 'corenlp_log.txt'))
            break
        except IOError:
            sleep(4)
        print "ERROR: Unable to find corenlp_log.txt"


    fname = ''
    while True:
        f.seek(0) # Refresh log.
        try:
            line = f.readlines()[-1]
        except IndexError:
            sleep(1)
            continue

        if line and line.strip().startswith('Annotating file'):
            # Once we find the right line, start the pbar
            if not pbar.has_started():
                print "Sending files to StanfordCoreNLP..."
                pbar.start()

            # Ensure corenlp is working on a new file
            new_fname = line.split('/')[-1].split(' ')[0]
            if pbar.has_started() and new_fname != fname:
                fname = new_fname
                pbar.tick()

        if pbar.is_done():
            # Stop the thread
            return
        sleep(.1)


def preprocess_dir(directory):
    """Removes unicode and makes temp files."""
    file_dict = {}
    # walk through directory
    for root, dirs, fnames in os.walk(directory):
        for f_name in fnames:
            fpath = os.path.join(root, f_name)
            f = codecs.open(fpath, 'r', 'utf-8')
            # open file
            if f_name.endswith('.json'):
                article_dict = json.load(f)

                #parse pub_date
                cal = pdt.Calendar()
                date = cal.parseDateText(article_dict['pub_date'])
                article_dict['pub_date'] = "{year}-{month}-{day}".format(
                        year=date[0], month=date[1], day=date[2])

            elif f_name.endswith('.txt'):
                article_dict = {
                    'author': 'N/A',
                    'title': 'N/A',
                    'publication': 'N/A',
                    'pub_date': 'N/A',
                    'content': f.read()
                    }

            article_dict['path'] = os.path.abspath(
                    os.path.join(root, f_name)).decode('utf-8')

            # remove unicode
            article_dict = dict((k, v.encode('ascii', 'ignore')) for (
                k, v) in article_dict.items())

            # make tempfile
            tf = tempfile.NamedTemporaryFile(dir=TEMP, delete=False)
            tf.write(article_dict['content'])

            # extract file name
            tname = tf.name.split('/')[-1]

            file_dict[tname] = article_dict

    return file_dict

def preprocess_iterable(iterable, parse_date=False):
    file_dict = {}
    # walk through directory
    for article_dict in iterable:
        #parse pub_date
        if parse_date:
            cal = pdt.Calendar()
            date = cal.parseDateText(article_dict['pub_date'])
            article_dict['pub_date'] = "{year}-{month}-{day}".format(
                    year=date[0], month=date[1], day=date[2])

        # remove unicode
        article_dict = dict((k, v.encode('ascii', 'ignore')) for (
            k, v) in article_dict.items())

        # make tempfile
        tf = tempfile.NamedTemporaryFile(dir=TEMP, delete=False)
        tf.write(article_dict['content'])

        # extract file name
        tname = tf.name.split('/')[-1]

        file_dict[tname] = article_dict

    return file_dict

def process_dir(directory, dbpath, memory='3g'):
    file_dict = preprocess_dir(directory)
    batch_process(file_dict, dbpath, memory)


def process_iterable(iterable, dbpath, memory='3g'):
    file_dict = preprocess_iterable(iterable)
    batch_process(file_dict, dbpath, memory)


def batch_process(file_dict, dbpath, memory):
    """Parses, resolves corefs, and extracts triplets from file in a
    directory.
    """
    from threading import Thread
    try:

        # Parse files with progress bar
        t = Thread(target=monitor_progress, kwargs={
            'num_files':len(file_dict)
            })
        t.daemon = True
        t.start()

        print "Starting corenlp. Wait a few moments."
        this_dir = os.path.dirname(os.path.realpath(__file__))
        corenlp_path = os.path.join(this_dir,
                "stanford-corenlp-full-2013-11-12")
        log_path = os.path.join(TEMP, 'corenlp_log.txt')
        parses = corenlp.batch_parse(TEMP, log_path, memory=memory,
                corenlp_path=corenlp_path)

        # Extract triplets and save to db
        pbar = ProgressBar(len(file_dict))
        file_name = ''
        for parse_dict in parses:
            if not pbar.has_started():
                print "Extracting triplets..."
                pbar.start()
            article_dict = file_dict[parse_dict['file_name']]

            # add article to db
            database.save_article(article_dict, dbpath)

            # resolve corefs and extract triplets
            triplets = process_parsed(parse_dict)

            # save triplet to db
            if len(triplets) > 0:
                for triplet in triplets:
                    triplet['article_path'] = article_dict['path']
                    triplet['pub_date'] = article_dict['pub_date']

                    database.save_triplet(triplet, dbpath)
            if parse_dict['file_name'] != file_name:
                file_name = parse_dict['file_name']
                pbar.tick()
    finally:  # remove temp files
        for root, dirs, fnames in os.walk(TEMP):
            for fname in fnames:
                p = os.path.join(root, fname)
                os.remove(p)


def process_parsed(parse_dict):
    """Takes any str and returns a list of triplet dicts."""
    # try:
    #     resolved_parsed = resolve_corefs(parse_dict)
    # except KeyError as e:
    #     # sometime parse_dict doesn't have a 'coref' key.
    #     # print e  # todo: better logging

    triplets = []
    for i, s in enumerate(parse_dict['sentences']):
        triplet = extract_triplet(parse_dict, i)
        if triplet:
            #remove unicode from triplet.
            triplet = dict((k, v.encode('ascii', 'replace')) for (
                k, v) in triplet.items())

            # record sentiment
            triplet['sentiment'] = sentiment_to_num(s['sentiment'])

            # record sentence
            triplet['sentence'] = list_to_sent(s['text'])

            triplets.append(triplet)
    return triplets

def list_to_sent(word_list):
    sentence = ' '.join(word_list)
    replacements = {
            ' !':'!',
            '$ ':'$',
            ' %':'%',
            '( ':'(',
            ' )':')',
            ' :':':',
            ' ;':';',
            ' ,':',',
            ' .':'.',
            ' ?':'?'
            }
    for old, new in replacements.iteritems():
        sentence = sentence.replace(old, new)

    return sentence


def sentiment_to_num(sentiment):
    """Takes the str sentiment from corenlp and returns its numerical
    equivalent.
    """
    sentiment_nums = {
        'Verypositive': 2,
        'Positive': 1,
        'Neutral': 0,
        'Negative': -1,
        'Verynegative': -2
        }

    return sentiment_nums[sentiment]


def resolve_corefs(parsed):
    """
    --DEPRECIATED--
    Uses corenlp coref data to replace mentions in a parsetree with their
    referents.

    The python wrapper for coreNLP returns a tuple containing
    the coref and numbers indicating its position.
    The format is as follows:
    ('coref', sentence_index, head_index, start_index, end_index)
    """
    PROP_NOUN_TAGS = ['NNP', 'NNPS']
    PRONOUN_TAGS = ['PRP', 'PRP$', 'WP', 'WP$']

    for corefs in parsed['coref']:
        for coref in corefs:
            # unpack some values
            referent = coref[1]
            referent_sentence = referent[1]
            referent_head = referent[2]
            referent_start = referent[3]
            referent_end = referent[4]
            mention = coref[0]
            mention_sentence = mention[1]
            mention_head = mention[2]
            mention_start = mention[3]
            mention_end = mention[4]
            mention_sent_list = parsed['sentences'][mention_sentence]['text']
            referent_sent_list = parsed['sentences'][referent_sentence]['text']

            #make trees
            referent_tree = Tree(
                parsed['sentences'][referent_sentence]['parsetree'])
            mention_tree = Tree(
                parsed['sentences'][mention_sentence]['parsetree'])

            # handle not found heads
            if referent_head == -1:
                # if the referent is one word long,
                # just use the start index
                if (referent_end - referent_start) == 1:
                    referent_head = referent_start
                else:
                    continue

            # if we have a valid head, check to make sure
            # non-words aren't making the head index isn't
            # mismatched with parsetree index.
            referent_head = fix_head_index(
                referent_head,
                parsed['sentences'][referent_sentence]['text']
                )

            if mention_head == -1:
                if (mention_end - mention_start) == 1:
                    mention_head = mention_start
                else:
                    continue

            # if we have a valid head, check to make sure
            # non-words aren't making the head index isn't
            # mismatch ed with parsetree index.
            mention_head = fix_head_index(
                mention_head,
                mention_sent_list)


            # if head index is out of the tree's range,
            # set the head index to be the last leaf in
            # the tree.
            # try:
            #     rtp = referent_tree.leaf_treeposition(referent_head)
            # except IndexError:
            #     referent_head = len(referent_tree.leaves())-1
            #     rtp = referent_tree.leaf_treeposition(referent_head)
            # try:
            #     mtp = mention_tree.leaf_treeposition(mention_head)
            # except IndexError:
            #     mention_head = len(mention_tree.leaves())-1
            #     mtp = mention_tree.leaf_treeposition(mention_head)

            # referent_leaf = get_leaf(rtp, referent_tree)
            # mention_leaf = get_leaf(mtp, mention_tree)
            rtp, referent_leaf = get_matching_leaf(
                    referent_head,
                    referent_sent_list[referent_head],
                    referent_tree
                    )
            mtp, mention_leaf = get_matching_leaf(
                    mention_head,
                    mention_sent_list[mention_head],
                    mention_tree
                    )


            # ensure that referent_leaf and mention_leaf
            # actually match their word.

            if mention_sent_list[mention_head] != mention_leaf[-1]:
                pass
                # print "WARNING: Mention leaf does not match mention."
                # consider adding a continue statement here


            # ensure referent and mention are unique
            if referent_leaf != mention_leaf:
                # ensure referents and mentions have the proper tags
                if referent_leaf.node in PROP_NOUN_TAGS and (
                        mention_leaf.node in PROP_NOUN_TAGS
                        or mention_leaf.node in PRONOUN_TAGS):

                    set_leaf(mtp, mention_tree, referent_leaf)
                    parsed['sentences'][mention_sentence]['parsetree'] = \
                        mention_tree.pprint()
    return parsed

def get_matching_leaf(head_index, word, tree):
    """Find the closest leaf to treeposition tp that matches word.
    Note: This function won't work if the word has already been changed
    by an earlier attempt to resolve coreferences"""
    head1 = head_index
    head2 = head_index
    try:
        tp = tree.leaf_treeposition(head_index)
    except IndexError:
        tp = tree.leaf_treeposition(len(tree.leaves())-1)
    tp1 = tp
    tp2 = tp
    leaf = get_leaf(tp, tree)
    leaf1 = leaf
    leaf2 = leaf
    for x in range(len(tree.leaves())):
        if word == leaf1[-1]:
            return tp1, leaf1
        elif word == leaf2[-1]:
            return tp2, leaf2
        else:
            head1 -= 1
            head2 += 1

            try:
                tp1 = tree.leaf_treeposition(head1)
            except IndexError:
                pass
            try:
                tp2 = tree.leaf_treeposition(head2)
            except IndexError:
                pass

            leaf1 = get_leaf(tp1, tree)
            leaf2 = get_leaf(tp2, tree)

    #leaf not found
    return tp, leaf


def fix_head_index(head, word_list):
    """Sometimes the index of word in the sentence returned by corenlp doesn't
    allign with the index of the word in its parse tree. The function attempts
    to fix by removing "non-words" from head's index value."""
    for word in word_list[0:head]:
        for char in word:
            is_word = False
            if char in string.letters + string.digits:
                # consider any word with at least
                # one letter or number to be a 'word'
                is_word = True
        if is_word is False:
            # the non word (probably) won't be in the
            # parsetree so, to make the indices match,
            # we subtract one from the the mention head
            head -= 1
    return head


def get_leaf(treeposition, tree):
    """Returns the leaf at a given tree position in tree."""
    for i in treeposition[0:-1]:
        tree = tree[i]
    return tree


def set_leaf(treeposition, tree, value):
    """Sets the leaf to some nltk.Tree value at treeposition in tree."""
    # iterate through second to last index
    for i in treeposition[0:-2]:
        tree = tree[i]

    tree[-1] = value

