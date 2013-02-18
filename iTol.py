#!/usr/bin/env python
'''
Created on Feb 8, 2012

@author: Shareef M Dabdoub
'''
import util
import argparse
from collections import defaultdict, namedtuple
import json

def otu_name(biom_row):
    tax = biom_row['metadata']['taxonomy']
    for i, lvl in enumerate(tax):
        if i < len(tax) - 1 and len(tax[i + 1].strip()) == 3:
            return 'Unclassified_' + lvl.split('_')[-1]
        elif i == len(tax) - 1:
            return lvl.split('_')[-1]


def relative_abundance(biom, filterIDs):
    ra = {item['id']: defaultdict(int) for item in biom['columns'] 
           if item['id'] in filterIDs}
    totals = defaultdict(float)
    
    for row, col, amt in biom['data']:
        oname = otu_name(biom['rows'][row])
        sampleID = biom['columns'][col]['id']
        
        if sampleID in filterIDs:
            ra[sampleID][oname] = amt
            totals[sampleID] += amt
    
    return {sid: {oid: ra[sid][oid] / totals[sid] for oid in ra[sid]} 
              for sid in ra}


def mean_otu_pct_abundance(ra, otuids):
    sids = ra.keys()
    otumeans = defaultdict(int)
    
    for oid in otuids:
        otumeans[oid] = sum([ra[sid][oid] for sid in sids 
                               if oid in ra[sid]]) / len(sids)
    
    return otumeans

def newick_replace_otuids(tree, biom):
    """
    Replace the OTU ids in the Newick phylogenetic tree format with truncated 
    OTU names 
    """
    for row in biom['rows']:
        tree = tree.replace(row['id'], otu_name(row))
    return tree


# Meant to contain all the data necessary for calculating a single column of 
# an iTol data table
DataCategory = namedtuple('DataCategory', 'sids ra means')

def gather_categories(imap, header, categories=None):
    """
    Find the user specified categories in the map and create a dictionary 
    to contain the relevant data for each type within the categories. Multiple
    categories will have their types combined such that each possible 
    combination will have its own entry in the dictionary.
    
    :@type imap: dict
    :@param imap: The input mapping file data keyed by SampleID
    :@type header: list
    :@param header: The header line from the input mapping file. This will be 
                    searched for the user-specified categories
    :@type categories: list
    :@param categories: The list of user-specified categories from the mapping 
                        file
    :@rtype: dict
    :@return: A dictionary keyed on the combinations of all the types found 
              within the user-specified categories. Each entry will contain an 
              empty DataCategory namedtuple. If no categories are specified, a 
              single entry with the key 'default' will be returned  
    """
    if categories is None:
        return {'default': DataCategory(frozenset(imap.keys()), None, None)}
    
    cat_ids = [header.index(cat) for cat in categories if cat in header
                                                         and '=' not in cat]
    conditions = {}
    for cat in categories:
        if '=' in cat and cat.split('=')[0] in header:
            conditions[header.index(cat.split('=')[0])] =  cat.split('=')[1]

    if not cat_ids:
        return {'default': DataCategory(frozenset(imap.keys()), None, None)}
    
    table = {}
    for sid,row in imap.iteritems():
        if all([row[c] == conditions[c] for c in conditions]):
            key = '_'.join([row[cid] for cid in cat_ids])
            if not key in table:
                table[key] = DataCategory(set(), None, None)
            table[key].sids.add(sid)
            
    return table


def handle_program_options():
    parser = argparse.ArgumentParser(description="Create files appropriate for \
                                     use in the iTol visualization program by \
                                     using the abundance data from a \
                                     biom-format file and groups specified in \
                                     a QIIME mapping file. The program also \
                                     modifies a Newick-format phylogenetic tree\
                                     file to use proper taxonomic names instead\
                                     of OTU IDs for useful display in iTol.")
    parser.add_argument('-i', '--otu_table', required=True,
                        help="The biom file with OTU-Sample abundance data.")
    parser.add_argument('-m', '--mapping', required=True,
                        help="The mapping file specifying group information \
                              for each sample.")
    parser.add_argument('-t', '--input_tre', required=True, 
                        help="A phylogenetic tree in Newick format to be \
                              modified by exchanging the OTU ID node names for \
                              taxonomic names.")
    parser.add_argument('-e', '--output_tre', default='iTol.tre',
                        help="The output .tre file")
    parser.add_argument('-o', '--output_itol_table', default='iTol_table.txt',
                        help="Other than a phylogenetic tree, the main input \
                              to iTol is a dataset file containing some \
                              representation of the relative abundance of every\
                              OTU across the specified data groups. This \
                              program calculates either the (MRE) mean relative\
                              abundance (relative abundance of each sample \
                              combined to find the mean across OTUs) or the \
                              MRE normalized across the groups (the group MRE \
                              of each OTU divided by the sum for that OTU).")
    parser.add_argument('-c', '--map_categories', default=None,
                        help="Any mapping categories, such as treatment type, \
                              that will be used to group the data in the output\
                              iTol table. For example, one category with three\
                              types will result in three data columns in the \
                              final output. Two categories with three types \
                              each will result in six data columns. Default \
                              is no categories and all the data will be treated\
                              as a single group.")
    parser.add_argument('-N', '--normalized_MRE', default=False, 
                         help="Specifies whether the mean relative abundance \
                                calculated for each OTU and group is normalized\
                                by the sum for the whole OTU. Default is \
                                False.")
#    parser.add_argument('-L', '--phylogenetic_level', default='s',
#                        choices=['k', 'p', 'c', 'o', 'f', 'g', 's'],
#                        help="Set the phylogenetic level at which to calculate\
#                              the mean relative abundance values. Defaults to \
#                              species level.")
#    parser.add_argument('-v', '--verbose', action='store_true')
    
    return parser.parse_args()


def main():
    args = handle_program_options()
    
    # input data
    with open(args.otu_table) as bF:
        biom = json.loads(bF.readline())
    with open(args.input_tre) as treF, open(args.output_tre, 'w') as outF:
        outF.write(newick_replace_otuids(treF.readline(), biom))
    imap = util.parse_map_file(args.mapping)
    with open(args.mapping, 'rU') as mapF:
        map_header = mapF.readline()[1:].split()
    
    groups = gather_categories(imap, map_header, args.map_categories)
    all_otus = {otu_name(item) for item in biom['rows']}

    for group in groups.values():
        group.ra = relative_abundance(biom, group.sids)
        group.means = mean_otu_pct_abundance(group.ra, all_otus)
    
    with open('iTol_table.txt', 'w') as itolF:
        itolF.write('LABELS\t' + '\t'.join([groups.keys()])+'\n')
        itolF.write('COLORS\t#ff0000\t#00ff00\n')
        
        for oname in all_otus:
            row = ['{name}']#\t{s:.2f}\t{ns:.2f}\n'
            row_data = {'name': oname}
            for name, group in groups.iteritems():
                row.append('{{{}:.2f}}'.format(name))
                if oname in group.means:
                    row_data[name] = group.means[oname] * 100 
                else:
                    row_data[name] = 0.0
            
            itolF.write('\t'.join(row).format(**row_data) + '\n')
            
if __name__ == '__main__':
    main()
