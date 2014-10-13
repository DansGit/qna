![A network graph](https://raw.githubusercontent.com/DansGit/qnatool/master/docs/abortion2.png)
# qnatool
This is a program for turning words (sentences, paragraphs, etc) into networks.
qnatool was inspired by the work of Roberto Franzosi (*From Words to Numbers: Narrative, Data, and Social Science*)
and Saatviga Sudhahar (*Automating Quantitative Narrative Analysis of News Data*) and does its best to follow their
examples for doing quantitative narrative analysis. 

I should add that this program represents my first steps into
the world of text analysis, so you should proceed with caution 
and skepticism if you decide to try this thing out.
Lastly, I'm very interested in both methodological feedback
(can we learn anything using this?) and critques of my very unprofessional code. 

# Features
* Sporadic documentation and messy code! (see todo)
* Support for .txt files and .json files (see usage)
* Generates a database of SVO triplets.
* Produces gexf files that can be viewed in Gephi.

# Setting Up
Make sure you have all the requirements installed before trying to use qnatool.
## Python 2.7
Make sure you have Python 2.7 installed.
To download it, go here: https://www.python.org/downloads/ 

## igraph
Go to http://igraph.org/python/ and install igraph to your computer.
Alternatively, if you use Ubuntu Linux, simply open your terminal and type in:
```bash
sudo apt-get install python-igraph
```
Or use whatever packagement method works for your distribution.

## Cairo Library
You need both Cairo Library and Py2cairo installed if you want qnatool to make images of the graph.
If not, you can skip this step.
* **CairoLib:** Go to http://www.cairographics.org/download/ and follow their instructions.
* **Py2cairo:** Got to http://cairographics.org/pycairo/ and follow their instructions.

Alternatively use whatever package management systems works for you.

#### Mac OS X
I've found it can be hard to install Py2cairo on OS X.
These instructions seem to work pretty well: http://pydanny.com/installing-pycairo-on-mountain-lion.html


## Stanford CoreNLP
Download Stanford CoreNLP and extract it to the root of your qnatool directory.

Download: http://nlp.stanford.edu/software/stanford-corenlp-full-2013-11-12.zip

Note: It must be this specific version of CoreNLP. Don't try to use a newer version.

Linux users can simply open a terminal and type in:
```bash
cd /path/to/qnatool
wget http://nlp.stanford.edu/software/stanford-corenlp-full-2013-11-12.zip
unzip stanford-corenlp-full-2013-11-12.zip
```

## Other requirements
Lastly, navigate to the qnatool directory and execute:
```bash
pip install -r requirements.txt
```

Now you should be ready to run qnatool!

# Usage
qnatool requires 3 things to run:

1. A project name.

2. A directory filled with files to process.

3. A directory where the results will be saved to.

Imagine you have a directory with .txt or .json (see json section) files that you want to turn into a single network.
Simply open a terminal, navigate to your qnatool directory and type in something like the following:
```bash
python qnatool.py project_name /directory/with/your/source/files /your/output/directory
```
This will create a new folder called 'project_name' in /your/output/directory.

# .json files
You can optionally choose to provide your source data as .json files, which gives qnatool a little more data to work with.
The json files are dictionary like objects that look like this:
```python
{
    "content": "The news article content goes here.",
    "title": "Article Title",
    "pub_date": "publicatation date of the article (see note below)",
    "publication": "The articles publisher",
    "author": "The article's author"
}
```
Currently, only pub_date is used in the program, but the other attributes are stored in your project's database for easy
access later on.

####A note on publication dates 
qnatool uses the parsedatetime module by Mike Taylor and Darshana Chhajed. This means
you can write the publication date in variety of formats (ex April, 1, 2014 or 4/1/14, etc) and it will be understood
by qnatool. More info here: https://code.google.com/p/parsedatetime/

# Todo
- [ ] Better documentation and clean up code.
- [ ] Add support for more metrics.
- [ ] Investigate using threads to speed up triplet extraction phase.
- [ ] Write a section about the results of the program in README.md
- [ ] The charting functions are pretty ugly and I'm not sure if they're at all useful.
I think I'll just remove them at some point and improve the spreadsheets that are generated so users can
make whatever charts they want.

