from nltk.tree import ParentedTree
from string import join

NOUN_TAGS = ['NN','NNP','NNPS','NNS']
VERB_TAGS = ['VB','VBD','VBG','VBN','VBP','VBZ']
ADJ_TAGS = ['JJ','JJR','JJS']

def extract_triplet(parse_dict, sent_index):
    """Extracts an SVO triplet from the sentence at sent_index in parse_dict.

        args:
                sentence (str): The sentence from which to extract triplets.

        returns:
                dict. A dictionary with the extracted triplets.
                Looks like this:
                {
                        'subject':'the subject',
                        'predicate':'the predicate',
                        'obj':'the object'
                }
    """
    tree = ParentedTree(parse_dict['sentences'][sent_index]['parsetree'])

    # attempt extraction with ner detection first
    # then use the Rusu algorithm.
    subject = _ner_extract(parse_dict, sent_index, lookfor='subject')
    if subject is not None:
        subject_is_named = '1' # true
    else:
        subject_is_named = '0' # false
        # fall back to old method
        subject = _extract_subject(tree)
    if subject is not None:
        predicate = _extract_predicate(tree)
        if predicate is not None:
            obj = _ner_extract(parse_dict, sent_index, lookfor='object')
            if obj is not None:
                obj_is_named = '1' # true
            else:
                obj_is_named = '0' # false
                # fall back to old method
                obj = _extract_object(predicate)
            if obj is not None:
                # combine results into one dictionary
                svo = {
                    'subject':subject,
                    'subj_named':subject_is_named,
                    'predicate':predicate,
                    'obj':obj,
                    'obj_named':obj_is_named
                }
                # take out the ParentedTrees, we're done with them
                svo = strip_trees(svo) # hehe sounds like 'strip tease' ;)
                return svo

def _ner_extract(parse_dict, sent_index, lookfor):
    # Get the deepest verb index
    tree = ParentedTree(parse_dict['sentences'][sent_index]['parsetree'])

    named_entities = get_named_entities(parse_dict, sent_index)

    deepest_verb = _get_deepest(tree, VERB_TAGS)
    if deepest_verb:
        deepest_verb_index = tp_to_index(deepest_verb.treeposition(), tree)
    else:
        return None

    for entity, start_index in named_entities:
        if lookfor == 'subject':
            if start_index < deepest_verb_index:
                return entity
        elif lookfor == 'object':
            if start_index >= deepest_verb_index:
                return entity

    # if no entity has been found so far, look for corefs

    # check if parse_dict has any corefs
    if not parse_dict.has_key('coref'):
        return None

    for corefs in parse_dict['coref']:
        for coref in corefs:
            mention = coref[0]
            mention_sentence = mention[1]
            mention_start = mention[3]
            referent = coref[1]

            if mention_sentence == sent_index:
                if lookfor == 'subject':
                    if mention_start < deepest_verb_index:
                        referent_named_entity = ner_coref_resolve(
                                referent,
                                parse_dict
                                )
                        if referent_named_entity is not None:
                            return referent_named_entity
                elif lookfor == 'object':
                    if mention_start >= deepest_verb_index:
                        referent_named_entity = ner_coref_resolve(
                                referent,
                                parse_dict
                                )
                        if referent_named_entity is not None:
                            return referent_named_entity


def ner_coref_resolve(referent, parse_dict):
    referent_sentence = referent[1]
    referent_start = referent[3]
    referent_entities = get_named_entities(parse_dict, referent_sentence)

    for entity, start_index in referent_entities:
        #if referent is a named entity:
        if referent_start >= start_index \
                and referent_start <= start_index + len(entity.split()):
            return entity


def get_named_entities(parse_dict, sent_index):
    """Returns a list of strings of named entities of the same kind
    and the index of their first word."""

    NER_TYPES = ['ORGANIZATION', 'PERSON']
    named_entities = []
    prev_tag = None
    entity = []
    start_index = None

    count = 0
    for word, d in parse_dict['sentences'][sent_index]['words']:
        # are we part of a string of words of the same kind?
        if d['NamedEntityTag'] == prev_tag:
            if d['NamedEntityTag'] in NER_TYPES:
                entity.append(word)

        # indicates start of a new entity
        elif d['NamedEntityTag'] in NER_TYPES:
            # save the previouse entity
            if entity != []:
                named_entities.append(
                        (' '.join(entity), start_index)
                        )
            entity = []
            entity.append(word)

            start_index = count

        prev_tag = d['NamedEntityTag']

        count += 1

    if entity != []:
        named_entities.append(
                (' '.join(entity), start_index)
                )


    return named_entities




def tp_to_index(tp, tree):
    """Finds the corrosponding index of a word in a sentence given
    its treeposition and tree."""

    for index in range(len(tree.leaves())):
        if tp == tree.leaf_treeposition(index)[:-1]:
            return index

def _extract_subject(tree):
    """Extracts the subject from a nltk ParentedTree.

        args:
                tree (ParentedTree): An nltk parse tree of the sentence.

        returns:
                list. Each item is a ParentedTree whose leaf is a noun
                        in the nouns the form the sentence's subject.
                None. Subject extraction failed.
    """
    NP_subtree = _get_first_child(tree, ['NP'])
    if not NP_subtree:
        return

    subject = _get_first_child(NP_subtree, NOUN_TAGS)
    if subject:
        phrase = _get_right_siblings(subject, NOUN_TAGS)
        phrase.insert(0, subject)
        return phrase

def _extract_predicate(tree):
    """Extracts the predicate from a nltk ParentedTree.

    args:
            tree (ParentedTree): A nltk parse tree of the sentence.

    returns:
            list. List of ParentedTrees whose leaves represent the
                    predicate and particle of the sentence.
            ParentedTree. A ParentedTree whose leaf represents the
                    predicate of the sentence.
            None. Predicate extraction failed.

    """
    VP_subtree = _get_first_child(tree, ['VP'])
    if not VP_subtree:
        return

    PARTICLE_TAGS = ['PRT', 'RP']
    predicate = _get_deepest(VP_subtree, VERB_TAGS)
    if predicate:
        if predicate.right_sibling() \
                and predicate.right_sibling().node in PARTICLE_TAGS:
            l = []
            l.append(predicate)
            l.append(predicate.right_sibling())
            return l
        return predicate

def _extract_object(predicate):
    """Extracts the predicate from a nltk ParentedTree.

    args:
            tree (ParentedTree): The predicate of sentence.
            Can be found by _extract_predicate.

    returns:
            list. A list of ParentedTrees whose leaves form the object
            of the sentence.
            ParentedTree. A parentedTree whose leaf is the object
            of the sentence.
    """
    PHRASE_TAGS = ['NP', 'PP', 'ADJP']
    if type(predicate) == list:
        predicate = predicate[0]

    siblings = _get_right_siblings(predicate, PHRASE_TAGS)
    obj = None
    for value in siblings:
        if value.node == 'NP' or value.node == 'PP':
            obj = _get_first_child(value, NOUN_TAGS)
        else:
            obj = _get_first_child(value, ADJ_TAGS)
    #get following nouns
    if obj:
        phrase = _get_right_siblings(obj, NOUN_TAGS)
        if phrase:
            phrase.insert(0, obj)
            return phrase
        else:
            return obj

#===========Uitility Functions===========#
def _get_first_child(tree, types):
    """Finds the first child of a certain typee in a ParentedTree.

    args:
            tree (ParentedTree): The tree in which to look.
            types [list]: The types (given by tree.node) that child must match.
                    ex. ['NP', 'VP', 'JJ']

    returns:
            ParentedTree. The first child of the given type.
            None. No child found.
    """
    for child in tree.subtrees(filter=lambda x: x.node in types):
        return child

def _get_right_siblings(child, types):
    """Returns a list of siblings of certain types positioned to the right
            of child in the ParentedTree. Stops when a sibling not in types
            is encountered.

            args:
                    child (ParentedTree): The child of whom to find right
                    siblings.
                    types (list): A list of types that the sibling has to match.
            returns:
                    list. The right siblings. List will be empty if no right
                    siblings are found.
        """
    go = True
    sibs = []
    while go:
        if child.right_sibling() and child.right_sibling().node in types:
            sibs.append(child.right_sibling())
            child = child.right_sibling()
        else:
            go = False
    return sibs

def _get_deepest(tree, types):
    """Find the deepest child in a given tree whose type is in types.

    args:
            tree (ParentedTree): The tree in which to search.
            types (list): A list of node types to search for.

    returns:
            ParentedTree. The tree whose leaf is the deepest child whose type
                    is in types.
            None. No tree whose type is in types was found.
    """
    depths = _get_deepest_recursive(tree, types)
    if not depths:
        return None
    top = 0
    deepest = None
    for t, level in depths:
        if level > top:
            top = level
            deepest = t
    if deepest:
        return deepest



def _get_deepest_recursive(t, types, depth=0, parent=None):
    """Recursive helper function for _get_deepest."""
    try:
        t.node
    except AttributeError:
        try:
            if parent.node in types:
                return (parent, depth)
        except AttributeError:
            pass

    else:
        children = []
        for child in t:
            grand_daughter = _get_deepest_recursive(child, types, depth+1, t)
            if grand_daughter:
                try:
                    children = children + grand_daughter
                except TypeError:
                    children.append(grand_daughter)
        return children


def strip_trees(svo):
    """
    Takes a dictionary generated by extract_triplets
    and removes all the trees in the dictionary,
    leaving behind only its text.
    Dictionary format:
    {
            'subject':'the subject',
            'verb':'The verb',
            'object':'The object',
    }
    """
    for key in svo:
        #make sure svo[key] is not none
        if svo[key]:
            #If there are multiple values, they'll be packaged in a list
            #If there is only one, the attribute won't be in a list.
            #If the attributes are in a list, we need to iterate over
            #the ParentedTrees in the list.
            if type(svo[key]) == list:
                attributes = []
                for ptree in svo[key]:
                    attributes.append(join(ptree.leaves(), " "))
                svo[key] = join(attributes, " ")
            #if the value is a ParentedTree
            else:
                try:
                    svo[key] = join(svo[key].leaves(), " ")
                except AttributeError:
                    svo[key] = svo[key]
    return svo


#============TESTS=============#
S = """
        (ROOT
                (S (CC But)
                    (NP (NNP Pope) (NNP Francis))
                    (VP (VBD sought)
                        (S
                            (VP (TO to)
                                (VP (VB play)
                                    (PRT (RP down))
                                    (NP
                                        (NP (DT the) (NN importance))
                                        (PP (IN of)
                                            (NP (PRP$ his) (NN invitation)))))))
                                        (, ,)
                                        (S
                                            (VP (VBG saying)
                                                (SBAR
                                                    (SBAR
                                                        (S
                                                            (NP (PRP he))
                                                            (VP (VBD was) (RB not)
                                                                (ADJP (VBN qualified)
                                                                    (S
                                                                        (VP (TO to)
                                                                            (VP (VB be)
                                                                                (NP (DT a) (NN mediator)))))))))
                                                                            (CC and)
                                                                            (SBAR (IN that)
                                                                                (S
                                                                                    (NP (JJ proper) (NNS negotiations))
                                                                                    (VP (VBD were)
                                                                                        (ADJP (JJ necessary)
                                                                                            (PP (IN for)
                                                                                                (NP (DT a) (NN peace) (NN deal)))))))))))
                                                                                            (. .)))
                """

#pprint(extract_triplets(S))

def test_get_deepest_recursive(S):
        tree = ParentedTree(S)
        VP_subtree = _get_first_child(tree, ['VP'])


        print _get_deepest(VP_subtree, VERB_TAGS)

#test_get_deepest_recursive(S)
