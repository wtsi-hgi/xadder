#!/usr/bin/env python3
################################################################################
# Copyright (c) 2017 Genome Research Ltd.
#
# Author: Joshua C. Randall <jcrandall@alum.mit.edu>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
################################################################################
import argparse
import xml.parsers.expat
import re
from pathlib import Path
from binascii import hexlify
from base64 import b64decode

class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class ParseFailure(Error):
    """Exception raised when parsing fails

    Attributes:
        message -- the reason for the parse failure
    """

    def __init__(self, message):
        self.message = message

class UnimplementedHandlerError(Error):
    """Exception raised when unexpected XML is present for which we have no handler.

    Attributes:
        data -- the XML data for which there was no handler
    """

    def __init__(self, data):
        self.data = data



def start_element_handler(name, attrs):
    print('Start element:', name, attrs)

def end_element_handler(name):
    print('End element:', name)

def char_data_handler(data):
    print('Character data:', repr(data))

def comment_handler(data):
    # Do not edit this comment tag:788956de-4f1b-46aa-8271-1048a2120d9f:10:äääää㌲ääãㄶäãä㍆ㄱä:ãääãä〰㉂ãã〸ããäã㈴ä
    tag = re.match(b'.*comment tag:([0-9a-f-]+):([0-9]+):(.*)$', data.encode('utf-8'), flags=(re.DOTALL))
    if tag:
        uuid = tag.group(1)
        num = tag.group(2)
        blob = tag.group(3)
        print('UUID: %s NUM: %s BLOB: %s BLOB(hex): %s' % (uuid, num, blob, hexlify(blob)))
        return
    # Do not edit this preview infomation:368699c4-0f05-457b-afce-daa16d5dd037:kFsBADwAPwB4AG0AbAAgAHYAZQByAHMAaQBvAG4APQAiADEALgAwACIAPwA+AA0ACgA8AFAA\n...
    preview = re.match(b'.*preview infor?mation:([0-9a-f-]+):(.*)', data.encode('utf-8'), flags=(re.DOTALL))
    if preview:
        uuid = preview.group(1)
        preview_data = b64decode(preview.group(2).replace(b'\n', b'')).decode('utf-16-le')
        preview_match = re.match('(.*)\001(.*)\000', preview_data, flags=(re.DOTALL))
        if not preview_match:
            raise ParseFailure("failed to parse preview")
        preview_header = preview_match.group(1).encode('utf-16-le')
        preview_xml = preview_match.group(2).replace('\r\n','\n').replace('\r','\n')
        # print('UUID: %s PREVIEW_HEADER(hex): %s PREVIEW_XML: %s' % (uuid, hexlify(preview_header), preview_xml))
        print('Have preview %s with header bytes %s' % (uuid, hexlify(preview_header)))
        parse_preview_xml(preview_xml)
        return
    print('Comment:', repr(data.encode('utf-8')))

def xml_decl_handler(version, encoding, standalone):
    print('XML declaration: %s %s %s' % (version, encoding, standalone))

def unimplemented_handler(data):
    if data in ["\n", "\r\n", "\r"]:
        return
    print('Unimplemented: %s' % hexlify(data.encode('utf-8')))
    #raise UnimplementedHandlerError(data)

def preview_start_element_handler(name, attrs):
    print('Preview Start element:', name, attrs)

def preview_end_element_handler(name):
    print('Preview End element:', name)

def preview_char_data_handler(data):
    print('Preview Character data:', repr(data))

def preview_comment_handler(data):
    print('Preview comment:', repr(data))

def preview_xml_decl_handler(version, encoding, standalone):
    print('Preview XML declaration: %s %s %s' % (version, encoding, standalone))

def preview_unimplemented_handler(data):
    if data in ["\n", "\r\n", "\r"]:
        return
    print('Preview Unimplemented: %s' % hexlify(data.encode('utf-8')))
    # raise UnimplementedHandlerError(data)

def parse_preview_xml(preview_xml):
    p = xml.parsers.expat.ParserCreate()
    p.buffer_text = True
    p.StartElementHandler = preview_start_element_handler
    p.EndElementHandler = preview_end_element_handler
    p.CharacterDataHandler = preview_char_data_handler
    p.CommentHandler = preview_comment_handler
    p.XmlDeclHandler = preview_xml_decl_handler
    p.DefaultHandler = preview_unimplemented_handler
    p.Parse(preview_xml)

def parse_xad_file(xad):
    p = xml.parsers.expat.ParserCreate()
    p.buffer_text = True
    p.StartElementHandler = start_element_handler
    p.EndElementHandler = end_element_handler
    p.CharacterDataHandler = char_data_handler
    p.CommentHandler = comment_handler
    p.XmlDeclHandler = xml_decl_handler
    p.DefaultHandler = unimplemented_handler
    with open(xad, mode='rb') as xad_file:
        p.ParseFile(xad_file)

def main():
    parser = argparse.ArgumentParser(description='Convert a chip data file from Bioanalyzer 2100')
    parser.add_argument('xad', help='the input chip data (XAD) file')
    args = parser.parse_args()

    parse_xad_file(args.xad)

if __name__ == "__main__":
    main()
