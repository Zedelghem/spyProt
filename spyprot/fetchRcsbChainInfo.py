#!/usr/bin/env python
# Copyright Michal Jamroz 2014, jamroz@chem.uw.edu.pl
import csv
import shutil
import tarfile
import urllib.request, urllib.error, urllib.parse
from os import makedirs, path
from xml.dom import minidom
from lxml import etree
from Bio.PDB import MMCIFIO, Select, PDBParser, PDBIO
from Bio.PDB.MMCIFParser import MMCIFParser


class ProteinFile:
    '''
       Base classs for download of PDB/CIF files from PDB Database and filter by chain and filter out HOH
       Supports also PDB Bundles when there are many subchains for a given protein
    '''

    def __init__(self, dir, pdbcode, chain=None, atom=None):
        self.pdbcode = pdbcode
        self.chain = chain
        self.dir = dir
        self.atom = atom


class ChainAndResidueSelect(Select):
    def __init__(self, chain, model=1, residue_out="HOH"):
        self.chain = chain
        self.model = model
        self.residue_out = residue_out

    def accept_model(self, model):
        if model is None or (model is not None and model.serial_num == self.model):
            return True
        else:
            return False

    def accept_chain(self, chain):
        if chain is None or (chain is not None and chain.id == self.chain):
            return True
        else:
            return False

    def accept_residue(self, residue):
        if residue.resname != self.residue_out and str(residue._id[0]).strip() == '':
            return True
        else:
            return False


class ChainSelect(Select):
    def __init__(self, chain, model=1, residue_out="HOH"):
        self.chain = chain
        self.model = model
        self.residue_out = residue_out

    def accept_chain(self, chain):
        if chain is None or (chain is not None and chain.id == self.chain):
            return True
        else:
            return False

    def accept_residue(self, residue):
        if residue.resname != self.residue_out and str(residue._id[0]).strip() == '':
            return True
        else:
            return False


class ChainAndAtomSelect(Select):
    def __init__(self, chain, model=1, residue_out="HOH", atom='CA'):
        self.chain = chain
        self.model = model
        self.residue_out = residue_out
        self.atom = atom

    def accept_chain(self, chain):
        if chain is None or (chain is not None and chain.id == self.chain):
            return True
        else:
            return False

    def accept_residue(self, residue):
        if residue.resname != self.residue_out and str(residue._id[0]).strip() == '':
            return True
        else:
            return False

    def accept_atom(self, atom):
        if atom is None or (atom is not None and atom.get_name() == self.atom):
            return True
        else:
            return False


class PdbFile(ProteinFile):
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

    def download(self):
        self.out_file = self.dir + '/' + self.pdbcode + '.pdb'
        try:
            makedirs(self.dir)
        except OSError as e:
            pass
        try:
            response = urllib.request.urlopen('https://files.rcsb.org/view/' + self.pdbcode.upper() + '.pdb')
            html = response.read().decode("UTF-8")
            with open(self.out_file, 'w') as myfile:
                myfile.write(html)
            if self.chain is not None:
                self.filter_by_chain()
        except urllib.error.HTTPError as e:
            print(self.pdbcode + " " + self.chain + " ...trying to download from PDB Bundle")
            response = urllib.request.urlopen('https://files.rcsb.org/pub/pdb/compatible/pdb_bundle/' + self.pdbcode.lower()[1:3] + '/' + self.pdbcode.lower() + '/' + self.pdbcode.lower() + '-pdb-bundle.tar.gz')
            tar = tarfile.open(fileobj=response, mode="r|gz")
            tar.extractall(self.dir)
            tar.close()
            mapFile, mapChain = self.parsePdbBundleChainIdFile(self.dir + '/' + self.pdbcode.lower() + '-chain-id-mapping.txt')
            newChain = mapChain.get(self.chain)
            pdbBundleFile = self.dir + '/' + mapFile.get(self.chain)
            if newChain!=self.chain:
                self.parsePdbAndTranslateChain(pdbBundleFile, self.chain, newChain)
            else:
                shutil.move(self.dir + '/' + mapFile.get(self.chain), self.out_file)
        if self.atom:
            self.filter_by_atom()
        return self.out_file

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
    def parsePdbAndTranslateChain(self, pdbFileIn, chain, newChain):
        #print chain + '->' + newChain
        self.out_file = self.out_file.replace(".pdb", "_" + self.chain + ".pdb")
        with open(pdbFileIn, "r", encoding='utf-8') as infile, open(self.out_file, "w", encoding='utf-8') as outfile:
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

    def filter_by_chain(self):
        parser = PDBParser()
        structure = parser.get_structure(self.pdbcode, self.out_file)
        io = PDBIO()
        io.set_structure(structure)
        self.out_file = self.out_file.replace(".pdb", "_" + self.chain + ".pdb")
        io.save(self.out_file, ChainAndResidueSelect(self.chain))
        del io

    def filter_by_atom(self):
        parser = PDBParser()
        structure = parser.get_structure(self.pdbcode, self.out_file)
        io = PDBIO()
        io.set_structure(structure)
        self.out_file = self.out_file.replace(".pdb", "_" + self.atom + ".pdb")
        io.save(self.out_file, ChainAndAtomSelect(chain=self.chain, atom=self.atom))
        del io


class MMCIFfile(ProteinFile):
    def download_only(self):
        self.cif_file = path.join(self.dir, self.pdbcode + ".cif")
        try:
            makedirs(self.dir)
        except OSError as e:
            pass
        response = urllib.request.urlopen('http://www.ebi.ac.uk/pdbe/entry-files/download/' + self.pdbcode + '.cif')
        html = response.read().decode("UTF-8")
        with open(self.cif_file, 'w') as myfile:
            myfile.write(html)

    def download(self):
        self.download_only()
        if self.chain is not None:
            self.filter_by_chain()
        else:
            self.out_file = self.cif_file
        if self.atom:
            self.filter_by_atom()
        return self.out_file

    def filter_by_chain(self):
        parser = MMCIFParser()
        structure = parser.get_structure(self.pdbcode, self.cif_file)
        io = MMCIFIO()
        io.set_structure(structure)
        self.out_file = self.cif_file.replace(".cif", "_" + self.chain + ".cif")
        io.save(self.out_file, ChainAndResidueSelect(self.chain))

    def filter_by_atom(self):
        parser = MMCIFParser()
        structure = parser.get_structure(self.pdbcode, self.cif_file)
        io = MMCIFIO()
        io.set_structure(structure)
        self.out_file = self.out_file.replace(".cif", "_" + self.atom + ".cif")
        io.save(self.out_file, ChainAndAtomSelect(chain=self.chain, atom=self.atom))
        del io

    def get_first_residue_id(self):
        parser = MMCIFParser()
        structure = parser.get_structure(self.pdbcode, self.cif_file)
        for ch in structure.get_chains():
            if ch.get_id() == self.chain:
                for residue in ch.get_residues():
                    return residue.get_id()[1]
        return 0

    def get_residue_list(self):
        parser = MMCIFParser()
        structure = parser.get_structure(self.pdbcode, self.cif_file)
        residues = {}
        for ch in structure.get_chains():
            if ch.get_id() == self.chain:
                for residue in ch.get_residues():
                    if residue.__dict__['resname'] != 'HOH':
                        residues[(residue.get_id()[1], residue.get_id()[2])] = residue.__dict__['resname']
        return residues


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


def fetchReleasedPdbs(from_date, to_date=''):
    '''
        Download list of pdb ids released in range from_date - to_date (or in day from_date). Return False if empty list
    '''
    if to_date == '':
        to_date = from_date
    '''
    date in format 2009-07-01
    '''
    url = 'http://www.rcsb.org/pdb/rest/search'
    queryText = """
<orgPdbCompositeQuery version="1.0">
<queryRefinement>
<queryRefinementLevel>0</queryRefinementLevel>
<orgPdbQuery>

<queryType>org.pdb.query.simple.ReleaseDateQuery</queryType>
<pdbx_audit_revision_history.revision_date.comparator>between</pdbx_audit_revision_history.revision_date.comparator>
<pdbx_audit_revision_history.revision_date.min>%s</pdbx_audit_revision_history.revision_date.min>
<pdbx_audit_revision_history.revision_date.max>%s</pdbx_audit_revision_history.revision_date.max>
<pdbx_audit_revision_history.ordinal.comparator>=</pdbx_audit_revision_history.ordinal.comparator>
<pdbx_audit_revision_history.ordinal.value>1</pdbx_audit_revision_history.ordinal.value>
</orgPdbQuery>
</queryRefinement>
<queryRefinement>
<queryRefinementLevel>1</queryRefinementLevel>
<conjunctionType>and</conjunctionType>
<orgPdbQuery>
<queryType>org.pdb.query.simple.ChainTypeQuery</queryType>
<description>Chain Type: there is a Protein chain</description>
<containsProtein>Y</containsProtein>
<containsDna>?</containsDna>
<containsRna>?</containsRna>
<containsHybrid>?</containsHybrid>
</orgPdbQuery>
</queryRefinement>
</orgPdbCompositeQuery>
    """ % (from_date, to_date)

    req = urllib.request.Request(url, data=queryText.encode("utf-8"), method='POST')
    f = urllib.request.urlopen(req)
    result = [i.strip().decode("utf-8") for i in f.readlines()]
    f.close()
    if result:
        return result
    else:
        return False



