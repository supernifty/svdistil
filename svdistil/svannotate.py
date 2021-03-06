'''
Module      : Main
Description : The main entry point for the program.
Copyright   : (c) Bernie Pope, 2018
License     : BSD-2-Clause 
Maintainer  : bjpope@unimelb.edu.au
Portability : POSIX

Merge distilled SVs
'''

from argparse import ArgumentParser
import sys
import logging
import pkg_resources
import csv
from intervaltree import Interval, IntervalTree
from pathlib import Path
from copy import copy


EXIT_FILE_IO_ERROR = 1
EXIT_COMMAND_LINE_ERROR = 2
EXIT_TSV_FILE_ERROR = 3
DEFAULT_VERBOSE = False
DEFAULT_WINDOW = 50
# padding on either side of gene coordinates
DEFAULT_PAD = 2000
PROGRAM_NAME = "svannotate"


try:
    PROGRAM_VERSION = pkg_resources.require(PROGRAM_NAME)[0].version
except pkg_resources.DistributionNotFound:
    PROGRAM_VERSION = "undefined_version"


def exit_with_error(message, exit_status):
    '''Print an error message to stderr, prefixed by the program name and 'ERROR'.
    Then exit program with supplied exit status.

    Arguments:
        message: an error message as a string.
        exit_status: a positive integer representing the exit status of the
            program.
    '''
    logging.error(message)
    print("{} ERROR: {}, exiting".format(PROGRAM_NAME, message), file=sys.stderr)
    sys.exit(exit_status)


def parse_args():
    '''Parse command line arguments.
    Returns Options object with command line argument values as attributes.
    Will exit the program on a command line error.
    '''
    description = 'Merge distilled SVs'
    parser = ArgumentParser(description=description)
    parser.add_argument('--version',
                        action='version',
                        version='%(prog)s ' + PROGRAM_VERSION)
    parser.add_argument('--log',
                        metavar='LOG_FILE',
                        type=str,
                        help='record program progress in LOG_FILE')
    parser.add_argument('--annotations',
                        metavar='ANNOTATIONS',
                        required=True,
                        type=str,
                        help='annotation file')
    parser.add_argument('--pad',
                        metavar='PAD',
                        default=DEFAULT_PAD,
                        type=int,
                        help='number of bases of padding on either side of gene, default: {}'.format(DEFAULT_PAD))
    parser.add_argument('--window',
                        metavar='WINDOW',
                        default=DEFAULT_WINDOW,
                        type=int,
                        help='window size for cross chromosome breakends, default: {}'.format(DEFAULT_WINDOW))
    parser.add_argument('tsv_file',
                        metavar='TSV_FILE',
                        type=str,
                        help='Input TSV files')
    return parser.parse_args()


class AnnIntervals(object):
    def __init__(self):
        self.chroms = {}

    def add(self, chrom, start, end, val):
        if chrom not in self.chroms:
            self.chroms[chrom] = IntervalTree()
        tree = self.chroms[chrom]
        tree[start:end] = val

    def lookup(self, chrom, start, end):
        if chrom in self.chroms:
            return self.chroms[chrom][start:end+1]
        else:
            return set()


def read_annotations(pad, annotations_file):
    intervals = AnnIntervals()
    tiers = set()
    with open(annotations_file) as file:
        reader = csv.DictReader(file, delimiter='\t')
        for row in reader:
            this_tier = int(row['tier'])
            tiers.add(this_tier)
            val = (row['gene'], this_tier)
            this_start = int(row['start']) - pad 
            this_end = int(row['end']) + pad
            intervals.add(row['chrom'], this_start, this_end, val)
    return tiers, intervals


def print_variant(tiers, fieldnames, row, intersections):
    hits = {}
    for i in intersections:
        gene, tier = i.data
        if tier not in hits:
            hits[tier] = set()
        hits[tier].add(gene)
    output_fields = [row[f] for f in fieldnames]
    output_tiers = [x for l in [["1", ";".join(sorted(hits[t]))] if t in hits else ["0", ""] for t in tiers] for x in l]
    output_row = output_fields + output_tiers
    print("\t".join(output_row))

def annotate_variants(window, tiers, annotations, variants_filename):
    half_window = window // 2
    with open(variants_filename) as file:
        reader = csv.DictReader(file, delimiter='\t')
        fieldnames = reader.fieldnames
        sorted_tiers = sorted(tiers) 
        tier_headers = [x for l in [["tier" + str(t), "tier" + str(t) + " genes"]  for t in tiers] for x in l]
        output_headers = fieldnames + tier_headers
        print("\t".join(output_headers))
        for row in reader:
            chr1 = row['chr1']
            pos1 = int(row['pos1'])
            chr2 = row['chr2']
            pos2 = int(row['pos2'])
            if chr1 == chr2:
                intersections = annotations.lookup(chr1, pos1, pos2)
                print_variant(sorted_tiers, fieldnames, row, intersections)
            else:
                pos1_low = max(0, pos1 - half_window)
                pos1_high = pos1 + (half_window - 1)
                intersections1 = annotations.lookup(chr1, pos1_low, pos1_high)
                pos2_low = max(0, pos2 - half_window)
                pos2_high = pos2 + (half_window - 1) 
                intersections2 = annotations.lookup(chr2, pos2_low, pos2_high)
                print_variant(sorted_tiers, fieldnames, row, intersections1.union(intersections2))


def init_logging(log_filename):
    '''If the log_filename is defined, then
    initialise the logging facility, and write log statement
    indicating the program has started, and also write out the
    command line from sys.argv

    Arguments:
        log_filename: either None, if logging is not required, or the
            string name of the log file to write to
    Result:
        None
    '''
    if log_filename is not None:
        logging.basicConfig(filename=log_filename,
                            level=logging.DEBUG,
                            filemode='w',
                            format='%(asctime)s %(levelname)s - %(message)s',
                            datefmt='%m-%d-%Y %H:%M:%S')
        logging.info('computation started')
        logging.info('command line: %s', ' '.join(sys.argv))


def main():
    "Orchestrate the execution of the program"
    options = parse_args()
    init_logging(options.log)
    tiers, annotations = read_annotations(options.pad, options.annotations)
    annotate_variants(options.window, tiers, annotations, options.tsv_file)


# If this script is run from the command line then call the main function.
if __name__ == '__main__':
    main()
