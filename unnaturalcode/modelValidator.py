#!/usr/bin/python
#    Copyright 2013 Joshua Charles Campbell
#
#    This file is part of UnnaturalCode.
#    
#    UnnaturalCode is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    UnnaturalCode is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with UnnaturalCode.  If not, see <http://www.gnu.org/licenses/>.

from ucUtil import *
from unnaturalCode import *
from pythonSource import *
from mitlmCorpus import *
from sourceModel import *

from logging import debug, info, warning, error
from random import randint
from os import path

import csv
import runpy
import sys, traceback
from shutil import copyfile
from tempfile import mkstemp, mkdtemp
import os

from multiprocessing import Process, Queue
from Queue import Empty

virtualEnvActivate = os.getenv("VIRTUALENV_ACTIVATE", None)

print sys.path

nonWord = re.compile('\W+')

class HaltingError(Exception):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return repr(self.value)

def runFile(q,path):
    if not virtualEnvActivate is None:
      execfile(virtualEnvActivate, dict(__file__=virtualEnvActivate))
    try:
        runpy.run_path(path)
    except SyntaxError as se:
        ei = sys.exc_info();
        eip = (ei[0], str(ei[1]), traceback.extract_tb(ei[2]))
        try:
          eip[2].append(ei[1][1])
        except IndexError:
          eip[2].append((se.filename, se.lineno, None, None))
        q.put(eip)
        return
    except Exception as e:
        ei = sys.exc_info();
        info("run_path exception:", exc_info=ei)
        eip = (ei[0], str(ei[1]), traceback.extract_tb(ei[2]))
        q.put(eip)
        return
    q.put((None, "None", [(path, None, None, None)]))
    
class validationFile(object):
    
    def __init__(self, path, language, tempDir):
        self.path = path
        self.lm = language
        self.f = open(path)
        self.original = self.f.read()
        self.lexed = self.lm(self.original)
        self.scrubbed = self.lexed.scrubbed()
        self.f.close()
        self.mutatedLexemes = None
        self.mutatedLocation = None
        self.tempDir = tempDir
        r = self.run(path)
        info("Ran %s, got %s" % (self.path, r[1]))
        if (r[0] != None):
          raise Exception("Couldn't run file: %s because %s" % (self.path, r[1]))
        #runpy.run_path(self.path)
    
    def run(self, path):
        q = Queue()
        p = Process(target=runFile, args=(q,path,))
        p.start()
        try:
          r = q.get(True, 10)
        except Empty as e:
          r = (HaltingError, "Didn't halt.", [(path, None, None, None)])
        p.terminate()
        p.join()
        assert not p.is_alive()
        assert r[2][-1][2] != "_get_code_from_file"
        return r

    
    def mutate(self, lexemes, location):
        assert isinstance(lexemes, ucSource)
        self.mutatedLexemes = self.lm(lexemes.deLex())
        self.mutatedLocation = location
        
    def runMutant(self):
        (mutantFileHandle, mutantFilePath) = mkstemp(suffix=".py", prefix="mutant", dir=self.tempDir)
        mutantFile = os.fdopen(mutantFileHandle, "w")
        mutantFile.write(self.mutatedLexemes.deLex())
        mutantFile.close()
        r = self.run(mutantFilePath)
        os.remove(mutantFilePath)
        return r
        
class modelValidation(object):
    
    def addValidationFile(self, files):
          """Add a file for validation..."""
          files = [files] if isinstance(files, str) else files
          assert isinstance(files, list)
          for fi in files:
            vfi = validationFile(fi, self.lm, self.resultsDir)
            if len(vfi.lexed) > self.sm.windowSize:
              self.validFiles.append(validationFile(fi, self.lm, self.resultsDir))
    
    def genCorpus(self):
          """Create the corpus from the known-good file list."""
          for fi in self.validFiles:
            self.sm.trainLexemes(fi.scrubbed)
    
    def validate(self, mutation, n):
        """Run main validation loop."""
        trr = 0 # total reciprocal rank
        tr = 0 # total rank
        ttn = 0 # total in top n
        assert n > 0
        for fi in self.validFiles:
          assert isinstance(fi, validationFile)
          info("Testing " + fi.path)
          for i in range(0, n):
            mutation(self, fi)
            runException = fi.runMutant()
            if (runException[0] == None):
              exceptionName = "None"
            else:
              exceptionName = runException[0].__name__
            filename, line, func, text = runException[2][-1]
            if (fi.mutatedLocation.start.line == line):
              online = True
            else:
              online = False
            worst = self.sm.worstWindows(fi.mutatedLexemes)
            for j in range(0, len(worst)):
                #debug(str(worst[i][0][0].start) + " " + str(fi.mutatedLocation.start) + " " + str(worst[i][1]))
                if worst[j][0][0].start <= fi.mutatedLocation.start and worst[j][0][-1].end >= fi.mutatedLocation.end:
                    #debug(">>>> Rank %i (%s)" % (i, fi.path))
                    break
            info(" ".join(map(str, [mutation.__name__, j, fi.mutatedLocation.start.line, exceptionName, line])))
            if j >= len(worst):
              error(repr(worst))
              error(repr(fi.mutatedLocation))
              assert False
            self.csv.writerow([
              fi.path, 
              mutation.__name__, 
              j, 
              worst[j][1], 
              fi.mutatedLocation.type,
              fi.mutatedLocation.start.line,
              nonWord.sub('', fi.mutatedLocation.value), 
              exceptionName, 
              online,
              filename,
              line,
              func])
            self.csvFile.flush()
            trr += 1/float(i+1)
            tr += float(i)
            if i < 5:
                ttn += 1
        mrr = trr/float(len(self.validFiles) * n)
        mr = tr/float(len(self.validFiles) * n)
        mtn = ttn/float(len(self.validFiles) * n)
        info("MRR %f MR %f M5+ %f" % (mrr, mr, mtn))
            
    def deleteRandom(self, vFile):
        """Delete a random token from a file."""
        ls = copy(vFile.scrubbed)
        token = ls.pop(randint(0, len(ls)-1))
        vFile.mutate(ls, token)
            
    def insertRandom(self, vFile):
        ls = copy(vFile.scrubbed)
        token = ls[randint(0, len(ls)-1)]
        pos = randint(0, len(ls)-1)
        ls.insert(pos, token)
        token = ls[pos]
        vFile.mutate(ls, token)
            
    def replaceRandom(self, vFile):
        ls = copy(vFile.scrubbed)
        token = ls[randint(0, len(ls)-1)]
        pos = randint(0, len(ls)-2)
        oldToken = ls.pop(pos)
        ls.insert(pos, token)
        token = ls[pos]
        vFile.mutate(ls, token)
      
    def __init__(self, source=None, language=pythonSource, resultsDir=None, corpus=mitlmCorpus):
        self.resultsDir = ((resultsDir or os.getenv("ucResultsDir", None)) or mkdtemp(prefix='ucValidation-'))
        if isinstance(source, str):
            raise NotImplementedError
        elif isinstance(source, list):
            self.validFileNames = source
        else:
            raise TypeError("Constructor arguments!")

        assert os.access(self.resultsDir, os.X_OK & os.R_OK & os.W_OK)
        self.csvPath = path.join(self.resultsDir, 'results.csv')
        self.csvFile = open(self.csvPath, 'a')
        self.csv = csv.writer(self.csvFile)
        
        self.corpusPath = os.path.join(self.resultsDir, 'validationCorpus')
        self.cm = corpus(readCorpus=self.corpusPath, writeCorpus=self.corpusPath, order=10)
        self.lm = language
        self.sm = sourceModel(cm=self.cm, language=self.lm)
        self.validFiles = list()
        self.addValidationFile(self.validFileNames)
        self.genCorpus()

    def release(self):
        """Close files and stop MITLM"""
        self.cm.release()
        self.cm = None
        
    def __del__(self):
        """I am a destructor, but release should be called explictly."""
        assert not self.cm, "Destructor called before release()"

DELETE = modelValidation.deleteRandom
INSERT = modelValidation.insertRandom
REPLACE = modelValidation.replaceRandom

