import sqlite3

ARTICLE_TABLE = 'articles'
TRIPLET_TABLE = 'triplets'

def init_db(dbpath):
    """creates a database connection and creates our tables."""
    conn = sqlite3.connect(dbpath, isolation_level=None)
    create_article_table = """CREATE TABLE IF NOT EXISTS {}
                            (
                                    author VARCHAR(50),
                                    path VARCHAR(250),
                                    title VARCHAR(50),
                                    publication VARCHAR(50),
                                    pub_date DATE,
                                    content TEXT
                            );
                    """.format(ARTICLE_TABLE)
    create_triplet_table = """CREATE TABLE IF NOT EXISTS {}
                            (
                                    article_path INTEGER,
                                    sentence VARCHAR(400),
                                    subject VARCHAR(50),
                                    predicate VARCHAR(50),
                                    obj VARCHAR(50),
                                    pub_date DATE,
                                    subject_weight REAL,
                                    subj_named BOOLEAN,
                                    predicate_weight REAL,
                                    obj_weight REAL,
                                    obj_named BOOLEAN,
                                    sentiment INTEGER DEFAULT 0,
                                    is_reliable BOOLEAN DEFAULT 0
                            );
                        """.format(TRIPLET_TABLE)
    conn.execute(create_article_table)
    conn.execute(create_triplet_table)
    conn.commit()
    conn.close()

def save_article(article_dict, dbpath):
    conn = sqlite3.connect(dbpath)

    insert = """INSERT INTO {table}
    (author, path, title, publication, pub_date, content)
    VALUES (:author, :path, :title, :publication, :pub_date,
    :content);""".format(table=ARTICLE_TABLE)
    # params = (author, title, publication, pub_date, content)

    c = conn.execute(insert, article_dict)
    conn.commit()
    conn.close()



def save_triplet(triplet, dbpath):

    conn = sqlite3.connect(dbpath)

    insert = """INSERT INTO {}
    (article_path, sentence, subject, subj_named, predicate, obj, obj_named, pub_date, sentiment)
    VALUES (:article_path, :sentence, :subject, :subj_named, :predicate, :obj, :obj_named,
    :pub_date, :sentiment);""".format(TRIPLET_TABLE)

    conn.execute(insert, triplet)
    conn.commit()
    conn.close()
