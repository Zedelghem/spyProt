#!/usr/bin/env python
# Copyright Michal Jamroz 2014, jamroz@chem.uw.edu.pl
import csv
import shutil
import tarfile
import urllib.request, urllib.error, urllib.parse
from os import makedirs
from xml.dom import minidom
from lxml import etree


class PdbFile:
    '''
       Download PDB files from RCSB PDB Database and filter by chain
       Supports also PDB Bundles when there are many subchains for a given protein

       example:
       PdbFile("1j85", "A", "/tmp").download()

       Parameters
       ==========
       code: string - PDB ID
       chain: string
       path: string - where to store PDB file

    '''

    def __init__(self, code, chain, path):
        self.pdbcode = code
        self.chain = chain
        self.path = path

    def download(self):
        pdbFile = self.path + '/' + self.pdbcode + '.pdb'
        try:
            makedirs(self.path)
        except OSError as e:
            pass
        try:
            response = urllib.request.urlopen('https://files.rcsb.org/view/' + self.pdbcode.upper() + '.pdb')
            html = response.read().decode("UTF-8")
            with open(pdbFile, 'w') as myfile:
                myfile.write(html)
            if self.chain is not None:
                pdbFile = self.filter_by_chain(pdbFile, self.chain)
        except urllib.error.HTTPError as e:
            print(self.pdbcode + " " + self.chain + " ...trying to download from PDB Bundle")
            response = urllib.request.urlopen('https://files.rcsb.org/pub/pdb/compatible/pdb_bundle/' + self.pdbcode.lower()[1:3] + '/' + self.pdbcode.lower() + '/' + self.pdbcode.lower() + '-pdb-bundle.tar.gz')
            tar = tarfile.open(fileobj=response, mode="r|gz")
            tar.extractall(self.path)
            tar.close()
            mapFile, mapChain = self.parsePdbBundleChainIdFile(self.path + '/' + self.pdbcode.lower() + '-chain-id-mapping.txt')
            newChain = mapChain.get(self.chain)
            pdbBundleFile = self.path + '/' + mapFile.get(self.chain)
            if newChain!=self.chain:
                self.parsePdbAndTranslateChain(pdbBundleFile, pdbFile, self.chain, newChain)
            else:
                shutil.move(self.path + '/' + mapFile.get(self.chain),pdbFile)
        return pdbFile

    @staticmethod
    def parsePdbBundleChainIdFile(chainFile):
        with open(chainFile, encoding='utf-8') as fp:
            line = fp.readline()
            cnt = 1
            files = []
            mapChain = {}
            mapFile = {}
            actualFile = ''
            while line:
                line = line.strip().rstrip()
                cnt += 1
                if line.find('pdb-bundle')>=0:
                    actualFile = line[:-1]
                    files.append(actualFile)
                    line = fp.readline()
                    continue
                elif actualFile!='' and line!='':
                    mapping = line.split()
                    key = mapping[1].strip()
                    val = mapping[0].strip()
                    mapChain[key]=val
                    mapFile[key] = actualFile
                line = fp.readline()
            return mapFile, mapChain

    # Remapping chain for PDB bundles with many subchains
    def parsePdbAndTranslateChain(pdbFileIn,pdbFileOut,chain,newChain):
        #print chain + '->' + newChain
        with open(pdbFileIn, "r", encoding='utf-8') as infile, open(pdbFileOut, "w", encoding='utf-8') as outfile:
            reader = csv.reader(infile)
            for i, line in enumerate(reader):
                if line[0].find('ATOM')==0 or line[0].find('HETATM')==0:
                    newLine = list(line[0])
                    if newLine[21]==newChain:
                        if len(chain) > 2:
                            newLine += chain
                            newLine[21] = "%"
                        elif len(chain)>1:
                            newLine[20] = chain[0]
                            newLine[21] = chain[1]
                        else:
                            newLine[21] = chain
                        outfile.write("".join(newLine) + "\n")
                else:
                    outfile.write(line[0] + "\n")

    @staticmethod
    def filter_by_chain(pdbfile, chain):
        pdbfile_out = pdbfile.replace(".pdb", "_" + chain + ".pdb")
        with open(pdbfile_out, "w") as outfile, open(pdbfile) as file:
            for _, line in enumerate(file):
                if line.startswith("ATOM") or line.startswith("TER"):
                    if str(line[21]) == chain:
                        outfile.write(line)
                else:
                    outfile.write(line)
        return pdbfile_out


class getIdenticalChains:
    '''
       Find identical chains to a given one

       example:
       a = getIdenticalChains("2jlo",chain="A").get()

       Parameters
       ==========
       pdbcode: string - PDB ID
       chain: string
    '''

    def __init__(self, pdbcode, chain='A'):
        self.pdb = pdbcode.upper()
        self.chain = chain
        f = urllib.request.urlopen('http://www.rcsb.org/pdb/rest/describeMol?structureId='+self.pdb+'.'+self.chain)
        data = f.read()
        f.close()
        self.root = etree.fromstring(data)

    def get(self):
        d = self.root.xpath("//molDescription/structureId[@id='"+self.pdb+"'][@chainId='"+self.chain+"']/polymer/chain/@id")
        return d


class getSimilarChains:
    '''
       Find similar chains to a given one with sequence identity given as parameter

       example:
       a = getSimilarChains("2jlo",chain="A",identity=90).get()

       Parameters
       ==========
       pdbcode: string - PDB ID
       chain: string
       identity: int - (percentage) of sequence identity
    '''
    def __init__(self, pdb, chain='A', identity=40):
        chain = chain
        url = "http://www.rcsb.org/pdb/rest/sequenceCluster?cluster="+str(identity)+"&structureId="+pdb+"."+chain
        r = urllib.request.urlopen(url)
        data = r.read()
        r.close()
        try:
            xmldoc = minidom.parseString(data)
            self.items = [elt.getAttribute('name') for elt in xmldoc.getElementsByTagName('pdbChain')]
        except:
            self.items = [pdb.upper()+"."+chain]#.upper()]

    def get(self):
        return self.items


class getUniqChains:
    '''
       Find a list of unique chains for a given PDB id

       example:
       a = getUniqChains("2jlo").get()

       Parameters
       ==========
       pdbcode: string - PDB ID
    '''
    def __init__(self, pdbcode):
        self.pdb = pdbcode.upper()
        f = urllib.request.urlopen('http://www.rcsb.org/pdb/rest/describeMol?structureId='+self.pdb)
        data = f.read()
        f.close()
        self.root = etree.fromstring(data)

    def get(self):
        o = []
        d = self.root.xpath("//molDescription/structureId[@id='"+self.pdb+"']/polymer/@entityNr")
        for e in d:
            d2 = self.root.xpath("//molDescription/structureId[@id='"+self.pdb+"']/polymer[@entityNr='"+e+"']/chain/@id")
            o.append(d2[0])
        return o


if __name__ == "__main__":
    a = getIdenticalChains("2jlo", chain="A").get()
    print(a)
    a = getSimilarChains("2jlo",chain="A",identity=90).get()
    print(a)
    a = getUniqChains("2jlo").get()
    print(a)
    p = PdbFile("1j85", "A", "/tmp").download()