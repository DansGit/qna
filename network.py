import igraph as ig
import sqlite3
import config
from gexf import Gexf
from random import randrange
from datetime import date
from progressbar import ProgressBar

def make_graph(date_range=False, giant=False, show_pbar=True):
    conn = sqlite3.connect(config.DB)

    if date_range is False:
        query = """SELECT article_path, subject, predicate, obj, sentence,
        sentiment, pub_date, subj_named, obj_named
        FROM triplets
        WHERE is_reliable = 1"""
        triplets = conn.execute(query).fetchall()
    else:
        query = """SELECT article_path, subject, predicate, obj, sentence,
        sentiment, pub_date, subj_named, obj_named FROM triplets
        WHERE is_reliable = 1
        AND pub_date >= ?
        AND pub_date < ?"""
        params = (date_range[0], date_range[1])
        triplets = conn.execute(query, params).fetchall()

    G = ig.Graph(directed=True)

    if show_pbar:
        pbar = ProgressBar(len(triplets))
        pbar.start()

    # Generate graph
    for article_path, subject, pred, obj, sentence, sentiment, pub_date, \
            subj_named, obj_named in triplets:

        if subject.lower() != obj.lower():
            # Sentence = sentence.encode('ascii', 'ignore')
            add_igraph_vertex(subject, subj_named, G)
            add_igraph_vertex(obj, obj_named, G)
            add_igraph_edge(
                article_path, subject, pred, obj, sentence, sentiment, G)

        if show_pbar:
            pbar.tick()

    conn.close()
    if giant:
        return G.clusters(mode=ig.WEAK).giant()
    else:
        return G

def add_igraph_vertex(name, is_named, G):
    # add vertex for subject if it does not exist.
    try:
        v = G.vs.find(name=name)
        v['frequency'] += 1

    # Vertex doesn't exist. Let's add it!
    except (ValueError, KeyError):
        start, end = node_daterange(name)
        G.add_vertex(
                name=name,
                start=start,
                end=end,
                community=0,
                kind='key concept',
                frequency=1,
                color=[255, 255, 255])


    # Classify object as actor set its color to dark grey
    if is_named:
        v = G.vs.find(name=name)
        v['kind'] = 'actor'
        # Set color to grey.
        v['color'] = [100, 100, 100]


def add_igraph_edge(article_path, source, pred, target, sentence, sentiment, G):
    # add edge from subject to object if it
    # does not already exist.
    try:
        sid = G.vs.find(name=source).index
        tid = G.vs.find(name=target).index
        edge = G.es[G.get_eid(sid, tid)]

        # if get_eid does not raise an error,
        # then we assume the edge exists

        # Combine new edge with former
        edge['sentiment'] += sentiment
        edge['weight'] += 1
        edge['article_path'] = "{}, {}".format(edge['article_path'], article_path)
        edge['label'] = "{}, {}".format(edge['label'], pred)
        edge['sentences'] = "{}\n{}".format(edge['sentences'], sentence)

        if sentiment < 0:
            # Set negative color to red
            r = 255
            g = 0
            b = 0
        elif sentiment > 0:
            # Set positive color to blue
            r = 0
            g = 0
            b = 255

        if sentiment < 0 or sentiment > 0:
            #mix former color with new color
            edge['color'][0] = (edge['color'][0] + r) / 2
            edge['color'][1] = (edge['color'][1] + g) / 2
            edge['color'][2] = (edge['color'][2] + b) / 2

    # add new edge
    except ig._igraph.InternalError:
        if sentiment < 0:
            # Set negative color to red
            r = 255
            g = 0
            b = 0
        elif sentiment > 0:
            # Set positive color to blue
            r = 0
            g = 0
            b = 255
        elif sentiment == 0:
            # Set neutral color to purple
            r = 200
            b = 200
            g = 0

        start, end = edge_daterange(source, target)
        G.add_edge(
                article_path=article_path,
                source=source,
                target=target,
                start=start,
                end=end,
                sentences=sentence,
                label=pred,
                sentiment=sentiment,
                weight=1,
                color=[r, g, b]
                )


def community_modularity(G):
    """Find communities with louvain modularity."""
    from analyze.vtraag import louvain

    # remove 'key concepts' from H so that we
    # only find communities of actors.
    H = G.copy()
    try:
        concepts = G.vs.select(kind_eq='key concept')
    except KeyError:
        # No concepts exist.
        # Usually means graph is too small.
        return False
    H.delete_vertices([v.index for v in concepts])

    # `Find communities
    opt = louvain.Optimiser()
    vc = opt.find_partition(H, louvain.ModularityVertexPartition)

    # Add community attribute to graph and give vertices a
    # corrosponding color.
    for index, subgraph in enumerate(vc.subgraphs()):
        if len(subgraph.vs) > 1:
            index += 1
            rgb = get_color()
            for vertex in subgraph.vs:
                if vertex['kind'] != 'key concept':
                    v = G.vs.find(name=vertex['name'])
                    v['community'] = index
                    v['color'] = rgb


def community_graph(G, population=4, concept_degree=3):
    """Returns a graph in which each community in G has been
    aggregated into a single vertex.
    """
    try:
        G = G.clusters(mode=ig.WEAK).giant()
    except ValueError:
        # Unable to find giant
        # Graph probably too small
        pass

    from collections import defaultdict
    labels = defaultdict(dict)
    H = ig.Graph(directed=True)

    for v in G.vs:
        if v['kind'] == 'key concept':
            # Add all key concepts to H
            H.add_vertex(
                    name=v['name'],
                    label=v['name'],
                    kind=v['kind'],
                    frequency=v['frequency'],
                    color=v['color']
                    )

        elif v['community'] > 0:
            if len(G.vs.select(community=v['community'])) > population:
                # Combine v with its community
                try:
                    w = H.vs.find(name=v['community'])
                    w['frequency'] += v['frequency']
                except (ValueError, KeyError):
                    # add new community vertex
                    H.add_vertex(
                            name=v['community'],
                            kind='community',
                            community=v['community'],
                            frequency=v['frequency'],
                            color=v['color']
                            )

            # Record frequency of v so we can make the label
            labels[v['community']][v['name']] = v['frequency']


    # Set vertex labels in H
    for v in H.vs:
        label = ', '.join([x[0] for x in
            sorted(
                labels[v['name']].items(),
                key=lambda x: x[1],
                reverse=True)[:3]
            ])

        if v['kind'] != 'key concept':
            v['label'] = label

    # Add edges to H
    for edge in G.es:

        # Look for source vertex in H
        try:
            # Check if the source has a corrosponding
            # community vertex in H.
            source = H.vs.find(name=G.vs[edge.source]['community'])
        except (KeyError, ValueError):
            try:
                # Check if the source has a corrosponding
                # name in H, for key concepts.
                source = H.vs.find(name=G.vs[edge.source]['name'])
            except (KeyError, ValueError):
                # could not find community or key concept in H.
                continue

        # Look For target vertex in H
        try:
            # Check if target has a corrosponding
            # community vertex in H.
            target = H.vs.find(name=G.vs[edge.target]['community'])
        except (KeyError, ValueError):
            try:
                # Check if target of has a corrosponding
                # name in H, for key concepts.
                target = H.vs.find(name=G.vs[edge.target]['name'])
            except (KeyError, ValueError):
                # could not find community or key concept in H.
                continue

        # Add edge to H
        try:
            # Check if edge already exists in H
            # Throws error if none found.
            e = H.es.find(_source=source, _target=target)

            # Combine new edge with former
            e['sentiment'] += edge['sentiment']
            e['weight'] += edge['weight']
            e['label'] = '{}, {}'.format(e['article_path'], edge['article_path'])
            e['label'] = '{}, {}'.format(e['label'], edge['label'])
            e['sentences'] = '{} {}'.format(e['sentences'], edge['sentence'])

            # Mix new color with former
            e['color'][0] = (edge['color'][0] + edge['color'][0]) / 2
            e['color'][1] = (edge['color'][1] + edge['color'][1]) / 2
            e['color'][2] = (edge['color'][2] + edge['color'][2]) / 2


        except (ValueError, KeyError):
            # Add new edge to H
            H.add_edge(source, target,
                article_path=edge['article_path'],
                sentiment=edge['sentiment'],
                weight=edge['weight'],
                label=edge['label'],
                sentences=edge['sentences'],
                color=edge['color']
                )

    # Filter key concepts in H
    go = True
    while go:
        go = False
        for v in H.vs:
            if v['kind'] == 'key concept' and v.degree() < concept_degree:
                v.delete()
                go = True

    return H


def write_gexf(G, fpath):
    """Convert an igraph graph to a gexf file."""
    gexf = Gexf("QNATool", config.project_name)
    gexf_graph = gexf.addGraph(
            'directed', 'dynamic', config.project_name, timeformat='date')

    # add custom attributes to edges and nodes
    gexf_graph.addEdgeAttribute('article_path', 0,
            type='string',
            force_id='article_path')
    gexf_graph.addEdgeAttribute('sentiment', 0, force_id='sentiment')
    gexf_graph.addEdgeAttribute('sentences', 0,
            type='string',
            force_id='sentences')

    gexf_graph.addNodeAttribute('community', 0, force_id='community')
    gexf_graph.addNodeAttribute('kind', 0, type='string', force_id='kind')
    gexf_graph.addNodeAttribute('frequency', 0, force_id='frequency')

    for vertex in G.vs:
        add_gexf_node(vertex.index, G, gexf_graph)

    for source_id, target_id in G.get_edgelist():
        add_gexf_edge(source_id, target_id, G, gexf_graph)

    f = open(fpath, 'w')
    gexf.write(f)


def add_gexf_node(vid, G, gexf_graph):
    if not gexf_graph.nodeExists(vid):
        v = G.vs[vid]

        n = gexf_graph.addNode(
                id=str(vid),
                label=str(v['name']),
                r=str(v['color'][0]),
                g=str(v['color'][1]),
                b=str(v['color'][2])
                )

        if 'start' in v.attributes():
            # n.addAttribute('start', value=str(v['start']))
            n.start = str(v['start'])
        if 'end' in v.attributes():
            # n.addAttribute('end', value=str(v['end']))
            n.start = str(v['start'])

        if 'label' in v.attributes():
            n.label = str(v['label'])

        if 'community' in v.attributes():
            n.addAttribute('community', value=str(v['community']))
        n.addAttribute('kind', value=str(v['kind']))
        n.addAttribute('frequency', value=str(v['frequency']))

def add_gexf_edge(source, target, G, gexf_graph):
    # set edge color to grey
    eid = G.get_eid(source, target)
    edge = G.es[eid]

    # add edge
    e = gexf_graph.addEdge(
            id=str(eid),
            source=str(source),
            target=str(target),
            label=str(edge['label']),
            weight=str(edge['weight']),
            r=str(edge['color'][0]),
            g=str(edge['color'][1]),
            b=str(edge['color'][2])
            )
    e.addAttribute('article_path', value=str(edge['article_path']))
    e.addAttribute('sentiment', value=str(edge['sentiment']))
    e.addAttribute('sentences', value=edge['sentences'])

    if 'start' in edge.attributes():
        e.start = str(edge['start'])
    if 'end' in edge.attributes():
        e.end = str(edge['end'])




def get_color(mix=(255, 255, 255)):
    """Randomly generate a color. Mix in a given color for pleasing
    aesthetics.
    """
    r = (randrange(0, 225, 25) + mix[0]) / 2
    g = (randrange(0, 225, 25) + mix[1]) / 2
    b = (randrange(0, 225, 25) + mix[2]) / 2

    return [r, g, b]


# Date Utilities
def get_temporal_graphs():
    temporal_graphs = []
    date_list = listDates()

    for date_range in date_list:

        d = date(*[int(x) for x in date_range[0].split('-')])
        temporal_graphs.append(
                (make_graph(date_range, show_pbar=False), d)
                )

    return temporal_graphs


def dateRange():
    """Returns the most past and most recent dates in db table triplets"""
    conn = sqlite3.connect(config.DB)
    query = """SELECT pub_date from triplets
                WHERE is_reliable = 1
                ORDER BY pub_date ASC"""
    result = conn.execute(query).fetchall()
    start = result[0][0]
    end = result[-1][0]
    conn.close()
    return start, end


def listDates():
    """Returns a list of tuples of dates a month apart between first and last
    date in db.
    """
    start, end = dateRange()

    start_date = date(*[int(x) for x in start.split('-')])
    end_date = date(*[int(x) for x in end.split('-')])


    first_month = start_date.month
    last_month = (end_date.year-start_date.year)*12 + end_date.month-1


    #so ugly
    dates = ["{year}-{month}-{day}".format(year=yr, month=mn, day=1) \
                for (yr, mn) in
                    (
                       (
                           (m - 1) / 12 + start_date.year, # find year
                           (m - 1) % 12 + 1 # find month
                       )
                    for m in range(first_month, last_month)
                    )
            ]

    # put dates into 2 tuples each representing
    # a range from the begining to end of a month
    date_ranges = zip(dates[0::], dates[1::])
    return date_ranges


def node_daterange(entity):
    """returns date of first and last appearance of a given entity."""
    conn = sqlite3.connect(config.DB)
    query = """SELECT pub_date FROM triplets
    WHERE subject = ?
    OR obj = ?
    ORDER BY pub_date ASC;"""  # first result is most past

    params = (entity, entity)
    result = conn.execute(query, params).fetchall()
    conn.close()
    start = result[0][0]
    end = result[-1][0]
    return (start, end)


def edge_daterange(subject, obj):
    """Returns dates of earlieast appearance of subject or obj
    (whichever comes second) and last appearance of subject or
    obj (whichever comes first.) In other words, the duration
    of the edge is the the duration in of both the subject and
    obj nodes existing at the same time.
    """
    sub_start, sub_end = node_daterange(subject)
    obj_start, obj_end = node_daterange(obj)

    # Greater than means more past. We want the slightly more recent one.
    if sub_start > obj_start:
        start = obj_start
    else:
        start = sub_start

    # Less than means more recent. We want the sligtly less recent one.
    if sub_end < obj_end:
        end = obj_end
    else:
        end = sub_end

    return start, end


def pickle_graph(G, fpath=None):
    import os
    """Writes the graph as a pickled
    object."""

    if not fpath:
        fpath = os.path.join(config.output_dir,
                             config.project_name +
                             ".pickle"
                             )

    f = open(fpath, 'w')
    return G.write_pickle(f)
