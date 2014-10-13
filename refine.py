import sqlite3
import config
from os import path
from progressbar import ProgressBar
import corenlp



def get_freqs(column, conn):
    """
    Returns the frequency of distinct values in a given column.
    Returns a sqlite3.cursor
    object with the entity name and its count
    selected.
    """
    query = """SELECT {column}, COUNT({column}) as cnt FROM triplets
    GROUP BY {column}
    ORDER BY cnt DESC;""".format(column=column)

    return conn.execute(query)

def get_freq(value, column, conn):
    query = """SELECT COUNT({column}) as cnt FROM triplets
                            WHERE {column} = ?
                            GROUP BY {column}
                            ORDER BY cnt DESC;""".format(column=column)
    params = (value,)
    result = conn.execute(query, params).fetchone()
    if result:
        return result[0]


def get_bg(fg_conn, bg_conn):
    # determine sample size
    query1 = """SELECT COUNT(ROWID) FROM triplets"""
    N = fg_conn.execute(query1).fetchone()[0]

    # select a random subset of bg_db
    query2 = """SELECT subject, predicate, obj FROM triplets
    ORDER BY RANDOM()
    LIMIT ?;"""
    params = (N,)
    result = bg_conn.execute(query2, params).fetchall()

    return [x for y in result for x in y]


def set_reliable(frequency_threshold, unnamed_threshold):
    clear_reliable()

    query = "UPDATE triplets SET is_reliable = 1 WHERE ROWID = ?"
    conn = sqlite3.connect(config.DB, isolation_level=None)

    reliable = get_reliable(
            frequency_threshold, weight_threshold, unnamed_threshold)

    print "Setting reliable..."
    pbar = ProgressBar(len(reliable)) #len(reliable.fetchall()))
    pbar.start()
    for rowid in reliable:
        params = (rowid,)
        conn.execute(query, params)
        pbar.tick()

    conn.commit()
    conn.close()

    print "Done!"


def clear_reliable():
    query = "UPDATE triplets SET is_reliable = 0"
    conn = sqlite3.connect(config.DB)
    conn.execute(query)
    conn.commit()
    conn.close()


def get_reliable(frequency_threshold, weight_threshold, unnamed_threshold):
    """
    We define a reliable triplet as any that appears more than K
    times and in which at least two entities/actions have a weight
    of at least W.
    Additionally triplets that were found using NER detection are
    considered more reliable than those who weren't. Therefore,
    we only include triplets whose entities are either named or
    appear more than unamed_threshold times.
    """
    query = """SELECT ROWID, subject, subj_named, predicate, obj, obj_named
    FROM triplets
    WHERE (subject_weight >= :weight AND predicate_weight >= :weight)
    OR (predicate_weight >= :weight AND obj_weight >= :weight)
    OR (subject_weight >= :weight AND predicate_weight >= :weight AND obj_weight >= :weight)
    GROUP BY subject, predicate, obj
    HAVING COUNT(obj) >= :frequency
    ORDER BY COUNT(obj) DESC;"""

    params = {
    'weight':weight_threshold,
    'frequency':frequency_threshold
    }

    conn = sqlite3.connect(config.DB)
    result = conn.execute(query, params).fetchall()

    count = get_counts(conn)

    reliable = []
    for ROWID, subject, subj_named, predicate, obj, obj_named in result:
        if (subj_named or count[subject.lower()] >= unnamed_threshold)\
                and (obj_named or count[obj.lower()] >= unnamed_threshold):
            reliable.append(ROWID)

    conn.close()
    return reliable


def get_counts(conn):
    """Make a dictionary with each entity in the db as key and its total
    frequency (as both a subject and an object) as the value."""

    subj_query = """SELECT LOWER(subject) as subj, COUNT(subject) as subj_count
    FROM triplets
    GROUP BY subject"""
    obj_query = """SELECT LOWER(obj) as ob, COUNT(obj) as obj_count
    FROM triplets
    GROUP BY obj"""

    subj_result = conn.execute(subj_query).fetchall()
    obj_result = conn.execute(obj_query).fetchall()

    count = dict(subj_result)
    for obj, obj_count in obj_result:
        try:
            count[obj] += obj_count
        except KeyError:
            count[obj] = obj_count

    return count


def resolve_corefs():
    print "Resolving corefs..."
    # Get entities from db
    conn = sqlite3.connect(config.DB)
    entities = get_entities(conn)

    # Resolve corefs using StanfordCoreNLP
    parses = parse_corefs(entities)
    for parse in parses:
        set_corefs(parse, conn)


    # Resolve corefs using Levenshtein edit distance
    matches = fuzzy_strmatch(get_entities(conn))
    if len(matches) > 0:
        set_strmatches(matches, conn)

    conn.close()


def get_entities(conn):
    query = "SELECT subject, obj FROM triplets WHERE is_reliable = 1;"
    result = conn.execute(query).fetchall()
    # Add results to list and remove duplicates with set
    entities = list(set([j for i in result for j in i]))
    return entities


def parse_corefs(entities):
    from tempfile import NamedTemporaryFile
    import os

    # Sort the list by string length.
    entities.sort(key=len, reverse=True)

    # Put all entities in a txt file.
    entity_str = '. '.join(entities)

    temp = NamedTemporaryFile(dir=config.TEMP, delete=False)
    temp.write(entity_str)

    # And send it StanfordCoreNLP to resolve corefs.
    parses = corenlp.batch_parse(config.TEMP, memory=config.memory)

    # Clean out temp dir
    for root, dirs, fnames in os.walk(config.TEMP):
        for fname in fnames:
            p = os.path.join(root, fname)
            os.remove(p)

    return parses


def set_corefs(parse_dict, conn):
    try:
        for corefs in parse_dict['coref']:
            for coref in corefs:
                mention = coref[0][0]
                referent = coref[1][0]

                query = """UPDATE triplets
                SET {column}=:referent
                WHERE {column}=:mention;
                """
                params = {
                        'referent':referent.strip().strip('.'),
                        'mention':mention.strip().strip('.')
                        }
                # resolve corefs for subject column
                conn.execute(query.format(column='subject'), params)

                # do the same for obj column
               # params['column'] = 'obj'
                conn.execute(query.format(column='obj'), params)
        conn.commit()
    except KeyError as e:
        print "Coref resolution failed."


def fuzzy_strmatch(words, tolerance=1):
    """Returns a dictionary of matched words whose edit distance
    is less than tolerance."""
    from nltk.metrics import edit_distance
    from collections import defaultdict

    # Sort shortest to longest.
    words.sort(key=len)
    matches = defaultdict(list)

    for word1 in words:
        for word2 in words:
            ed = edit_distance(word1, word2)
            if word1 != word2 and ed <= tolerance:
                matches[word1].append(word2)

    return matches


def set_strmatches(matches, conn):
    """Takes a dict generated by fuzzy_strmatch and replaces words in
    the database with their match."""
    for referent, mentions in matches.iteritems():
        for mention in mentions:
            query = """UPDATE triplets
            SET {column}=:referent
            WHERE {column}=:mention;
            """
            params = {
                    'referent': referent,
                    'mention': mention
                    }

            # Replace corefs for subject column.
            conn.execute(query.format(column='subject'), params)

            # Do the same for obj column.
            conn.execute(query.format(column='obj'), params)
    conn.commit()









