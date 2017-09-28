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
from xml.dom.minidom import parse, parseString
import re
from pathlib import Path
from binascii import hexlify
from base64 import b64decode
import zlib
import struct

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

class UnexpectedNodeError(Error):
    """Exception raised when unexpected XML is present for which we have no handler.

    Attributes:
        node -- the DOM node for which we have no handler
        message -- a message regarding the context
    """

    def __init__(self, node, message):
        self.node = node
        self.message = message

class UnsupportedPackedValueType(Error):
    """Exception raised when the packed value type (e.g. for RawSignal elements) found in the XML is not supported.

    Attributes:
        var_type -- the var_type that is not supported
    """

    def __init__(self, var_type):
        self.var_type = var_type

def handle_header(decoded_text):
    # 020000004f00000038000000350000000a00000058006300650065006400530043004f002c003100300000000000000000000000000000000000000000000000000000000000000000000000
    # 020000004f000000102c6700ff4a16000a00000058006300650065006400530043004f002c003100300000000000000000000000000000000000000000000000000000000000000000000000
    header_int1 = int.from_bytes(decoded_text[0:4], byteorder='little')
    print("have header_int1 %d" % (header_int1))
    header_int2 = int.from_bytes(decoded_text[4:8], byteorder='little')
    print("have header_int2 %d" % (header_int2))
    header_int3 = int.from_bytes(decoded_text[8:12], byteorder='little')
    print("have header_int3 %d" % (header_int3))
    header_int4 = int.from_bytes(decoded_text[12:16], byteorder='little')
    print("have header_int4 %d" % (header_int4))
    header_int5 = int.from_bytes(decoded_text[16:20], byteorder='little')
    print("have header_int5 %d" % (header_int5))
    header_str1 = decoded_text[20:].decode('utf-16-le')
    print("have header_str1 %s" % (header_str1))

def xad_handle_comment(node):
    data = node.nodeValue
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
        # FIXME not sure what how this should be extracted - seems to be two bytes then a \000 or \001, then the XML
        preview_match = re.match('(.*)[\000\001](.*)\000', preview_data, flags=(re.DOTALL))
        if not preview_match:
            print("preview_data: %s\n%s\n" % (preview_data[0:80], preview.group(2).hex()))
            raise ParseFailure("failed to parse preview")
        preview_preamble = preview_match.group(1).encode('utf-16-le')
        preview_xml = preview_match.group(2).replace('\r\n','\n').replace('\r','\n')
        print('Have preview %s with preamble %s' % (uuid, hexlify(preview_preamble)))
        parse_preview_xml(preview_xml)
        return

    # Do not edit this header information:f85b47ac-6be2-4de6-9164-a077e5a0b247:AgAAAE8AAAA4AAAANQAAAAoAAABYAGMAZQBlAGQAUwBDAE8ALAAxADAAAAAAAAAAAAAAAAAA\n...
    header = re.match(b'.*header information:([0-9a-f-]+):(.*)', data.encode('utf-8'), flags=(re.DOTALL))
    if header:
        uuid = header.group(1)
        decoded = b64decode(header.group(2))
        handle_header(decoded[0:76])
        extra = decoded[76:]
        print("have extra header: 0x%s" % (extra.hex()))
        return

    raise UnexpectedNodeError(node, "Unexpected comment node at XAD top-level")

def get_text(node):
    if node.childNodes.length == 1:
        child = node.childNodes.item(0)
        if child.nodeType == node.TEXT_NODE:
            return child.data
        else:
            raise UnexpectedNodeError(child, "Not a text node")
    elif node.childNodes.length < 1:
        return ""
    else:
        raise UnexpectedNodeError(node, "More than one child node")

def get_table(node):
    if node.childNodes.length == 1:
        child = node.childNodes.item(0)
        if child.nodeName == "Table":
            print("TODO: process table %s" % child)
        else:
            raise UnexpectedNodeError(child, "Not a Table node")
    elif node.childNodes.length < 1:
        raise UnexpectedNodeError(node, "Table missing children")
    else:
        raise UnexpectedNodeError(node, "More than one child node for table")

# FIXME args
gel_image_filename = "gel_image.png"
compressed_data_filename = "compressed.data"

def handle_preview(node):
    # [<DOM Element: Title at 0x7f0c344ab470>, <DOM Element: ChipInfo at 0x7f0c344ab5a0>, <DOM Element: SamplesInfo at 0x7f0c34034340>, <DOM Element: GelImage at 0x7f0c3403a508>]
    for child in node.childNodes:
        if child.nodeName == "Title":
            print("Preview Title: %s" % get_text(child))
        elif child.nodeName == "ChipInfo":
            print("Preview ChipInfo: %s" % get_table(child))
        elif child.nodeName == "SamplesInfo":
            print("Preview SamplesInfo: %s" % get_table(child))
        elif child.nodeName == "GelImage":
            gel_image = b64decode(get_text(child))
            print("Writing Gel Image to %s" % gel_image_filename)
            with open(gel_image_filename, 'wb') as png:
                png.write(gel_image)
        else:
            raise UnexpectedNodeError(child, "Unexpected node under <Preview> element")

def parse_preview_xml(preview_xml):
    preview = parseString(preview_xml)
    preview.normalize
    for node in preview.childNodes:
        if node.nodeName == "Preview":
            handle_preview(node)
        else:
            raise UnexpectedNodeError(node, "Unexpected node in embedded Preview XML document")

def handle_dam_assay_setpoints(daas):
    assert daas.nodeName == "DAMAssaySetpoints"
    for child in daas.childNodes:
        if child.nodeName == "xxx":
            pass
        else:
            raise UnexpectedNodeError(child, "Unexpected node under <DAMAssaySetpoints> element")

def handle_da_assay_setpoints(daas):
    assert daas.nodeName == "DAAssaySetpoints"
    for child in daas.childNodes:
        if child.nodeName == "DAMAssaySetpoints":
            handle_dam_assay_setpoints(child)
        elif child.nodeName == "DAMAssayInfoCommon":
            print("DAMAssayInfoCommon: %s" % (child.toxml()))
        elif child.nodeName == "DAMAssayInfoMolecular":
            print("DAMAssayInfoMolecular: %s" % (child.toxml()))
        elif child.nodeName == "DAMDefaultAssayInfoMolecular":
            print("DAMDefaultAssayInfoMolecular: %s" % (child.toxml()))
        else:
            raise UnexpectedNodeError(child, "Unexpected node under <DAAssaySetpoints> element")

def handle_da_sample_setpoints(daas):
    assert daas.nodeName == "DASampleSetpoints"
    for child in daas.childNodes:
        if child.nodeName == "DAMIntegrator":
            print("DAMIntegrator: %s" % (get_text(child)))
        elif child.nodeName == "DAMPeakManipulation":
            print("DAMPeakManipulation: %s" % (child.toxml()))
        elif child.nodeName == "DAMAlignment":
            print("DAMAlignment: %s" % (child.toxml()))
        elif child.nodeName == "DAMConcentration":
            print("DAMConcentration: %s" % (child.toxml()))
        elif child.nodeName == "DAMSizing":
            print("DAMSizing: %s" % (child.toxml()))
        elif child.nodeName == "DAMFragment":
            print("DAMFragment: %s" % (child.toxml()))
        elif child.nodeName == "DAMCoMigration":
            print("DAMCoMigration: %s" % (child.toxml()))
        elif child.nodeName == "DAMCalibration":
            print("DAMCalibration: %s" % (child.toxml()))
        elif child.nodeName == "DAMSmearAnalysis":
            print("DAMSmearAnalysis: %s" % (child.toxml()))
        elif child.nodeName == "DAMRollingBallA":
            print("DAMRollingBallA: %s" % (child.toxml()))
        elif child.nodeName == "DAMRollingBallB":
            print("DAMRollingBallB: %s" % (child.toxml()))
        elif child.nodeName == "DAMSpikeRejectionA":
            print("DAMSpikeRejectionA: %s" % (child.toxml()))
        elif child.nodeName == "DAMSpikeRejectionB":
            print("DAMSpikeRejectionB: %s" % (child.toxml()))
        elif child.nodeName == "DAMBaseline":
            print("DAMBaseline: %s" % (child.toxml()))
        elif child.nodeName == "DAMCommon":
            print("DAMCommon: %s" % (child.toxml()))
        elif child.nodeName == "DAMStandardCurve":
            print("DAMStandardCurve: %s" % (child.toxml()))
        elif child.nodeName == "DAMSavitzkyGolay":
            print("DAMSavitzkyGolay: %s" % (child.toxml()))
        elif child.nodeName == "DAMMarkerDetection":
            print("DAMMarkerDetection: %s" % (child.toxml()))
        elif child.nodeName == "DAMMarkerThreshold":
            print("DAMMarkerThreshold: %s" % (child.toxml()))
        elif child.nodeName == "DAMLowerMarkerPresent":
            print("DAMLowerMarkerPresent: %s" % (get_text(child)))
        elif child.nodeName == "DAMBaselineSubstractionOld":
            print("DAMBaselineSubstractionOld: %s" % (child.toxml()))
        elif child.nodeName == "DAMBaselineSubstractionGolovin":
            print("DAMBaselineSubstractionGolovin: %s" % (get_text(child)))
        elif child.nodeName == "DAMLinearStretchY":
            print("DAMLinearStretchY: %s" % (get_text(child)))
        elif child.nodeName == "DAMMasterMarkerDetectionRNA":
            print("DAMMasterMarkerDetectionRNA: %s" % (get_text(child)))
        elif child.nodeName == "DAMSystemPeakDetection":
            print("DAMSystemPeakDetection: %s" % (get_text(child)))
        elif child.nodeName == "DAMTimeShift":
            print("DAMTimeShift: %s" % (get_text(child)))
        elif child.nodeName == "DAMPrepareRowData":
            print("DAMPrepareRowData: %s" % (get_text(child)))
        elif child.nodeName == "DAMIntegrator2":
            print("DAMIntegrator2: %s" % (child.toxml()))
        elif child.nodeName == "DAMFragment2":
            print("DAMFragment2: %s" % (get_text(child)))
        elif child.nodeName == "DAMDynamicMarkerDetection":
            print("DAMDynamicMarkerDetection: %s" % (child.toxml()))
        elif child.nodeName == "DAMNoiseCalculation":
            print("DAMNoiseCalculation: %s" % (child.toxml()))
        elif child.nodeName == "DAMDeconvolution":
            print("DAMDeconvolution: %s" % (child.toxml()))
        elif child.nodeName == "DAMNoiseFlagging":
            print("DAMNoiseFlagging: %s" % (child.toxml()))
        elif child.nodeName == "DAMDetailing":
            print("DAMDetailing: %s" % (child.toxml()))
        elif child.nodeName == "DAMPeakPercentOfTotal":
            print("DAMPeakPercentOfTotal: %s" % (child.toxml()))
        elif child.nodeName == "DAMIntegrationRefinement":
            print("DAMIntegrationRefinement: %s" % (child.toxml()))
        elif child.nodeName == "DAMLDLCalculation":
            print("DAMLDLCalculation: %s" % (child.toxml()))
        else:
            raise UnexpectedNodeError(child, "Unexpected node under <DASampleSetpoints> element")

def handle_da_ladder_sequence(dals):
    assert dals.nodeName == "DALadderSequence"
    for child in dals.childNodes:
        if child.nodeName == "DAMethod":
            print("DAMMethod: %s" % (child.toxml()))
        else:
            raise UnexpectedNodeError(child, "Unexpected node under <DALadderSequence> element")

def handle_assay_body(assay_body):
    assert assay_body.nodeName == "AssayBody"
    for child in assay_body.childNodes:
        if child.nodeName == "DAAssaySetpoints":
            handle_da_assay_setpoints(child)
        elif child.nodeName == "DASampleSequence":
            print("DASampleSequence: %s" % (child.toxml()))
        elif child.nodeName == "DASampleSetpoints":
            handle_da_sample_setpoints(child)
        elif child.nodeName == "DALadderSequence":
            handle_da_ladder_sequence(child)
        elif child.nodeName == "DALadderSetpoints":
            print("DALadderSetpoints: %s" % (child.toxml()))
        elif child.nodeName == "UISetpoints":
            print("UISetpoints: %s" % (child.toxml()))
        elif child.nodeName == "DADefaultSampleSequence":
            print("DADefaultSampleSequence: %s" % (child.toxml()))
        elif child.nodeName == "DADefaultSampleSetpoints":
            print("DADefaultSampleSetpoints: %s" % (child.toxml()))
        elif child.nodeName == "DADefaultLadderSequence":
            print("DADefaultLadderSequence: %s" % (child.toxml()))
        elif child.nodeName == "DADefaultLadderSetpoints":
            print("DADefaultLadderSetpoints: %s" % (child.toxml()))
        elif child.nodeName == "DAChipSequence":
            print("DAChipSequence: %s" % (child.toxml()))
        elif child.nodeName == "DAChipSetpoints":
            print("DAChipSetpoints: %s" % (child.toxml()))
        elif child.nodeName == "DADefaultChipSequence":
            print("DADefaultChipSequence: %s" % (child.toxml()))
        elif child.nodeName == "DADefaultChipSetpoints":
            print("DADefaultChipSetpoints: %s" % (child.toxml()))
        elif child.nodeName == "DefaultUISetPoints":
            print("DefaultUISetPoints: %s" % (child.toxml()))
        else:
            raise UnexpectedNodeError(child, "Unexpected node under <AssayBody> element")

def get_packed_values(packed_values):
    assert packed_values.nodeType == packed_values.ELEMENT_NODE
    num_values = int(packed_values.attributes.getNamedItem("numvalues").nodeValue)
    var_type = packed_values.attributes.getNamedItem("vartype").nodeValue
    if var_type == "LE_R4":
        unpack_format = 'f'
    elif var_type == "LE_I2":
        unpack_format = 'h'
    elif var_type == "LE_UI1":
        unpack_format = 'B'
    else:
        raise UnsupportedPackedValueType(var_type)
    encoded = get_text(packed_values)
    decoded = b64decode(encoded)
    values = struct.unpack('<%d%s' % (num_values, unpack_format), decoded)
    assert len(values) == num_values
    return values

def handle_voltage(name, voltage):
    assert voltage.nodeName == "Voltage"
    for child in voltage.childNodes:
        if child.nodeName == "HasData":
            print("%s HasData: %s" % (name, get_text(child)))
        elif child.nodeName == "SignalData":
            handle_signal_data("%s Voltage" % name, child)
        else:
            raise UnexpectedNodeError(child, "Unexpected node under %s Voltage element" % (name))

def handle_current(name, current):
    assert current.nodeName == "Current"
    for child in current.childNodes:
        if child.nodeName == "HasData":
            print("%s HasData: %s" % (name, get_text(child)))
        elif child.nodeName == "SignalData":
            handle_signal_data("%s Current" % name, child)
        else:
            raise UnexpectedNodeError(child, "Unexpected node under %s Current element" % (name))

def handle_channel(name, channel):
    assert channel.nodeName == "Channel"
    for child in channel.childNodes:
        if child.nodeName == "HasData":
            print("%s HasData: %s" % (name, get_text(child)))
        elif child.nodeName == "SignalData":
            handle_signal_data("%s Channel" % name, child)
        else:
            raise UnexpectedNodeError(child, "Unexpected node under %s Channel element" % (name))

def handle_signal_data(name, signal_data):
    assert signal_data.nodeName == "SignalData"
    for child in signal_data.childNodes:
        if child.nodeName == "AlignmentBias":
            print("%s AlignmentBias: %s" % (name, get_text(child)))
        elif child.nodeName == "AlignmentScale":
            print("%s AlignmentScale: %s" % (name, get_text(child)))
        elif child.nodeName == "ChannelID":
            print("%s ChannelID: %s" % (name, get_text(child)))
        elif child.nodeName == "Index":
            print("%s Index: %s" % (name, get_text(child)))
        elif child.nodeName == "MaxValue":
            print("%s MaxValue: %s" % (name, get_text(child)))
        elif child.nodeName == "MinValue":
            print("%s MinValue: %s" % (name, get_text(child)))
        elif child.nodeName == "Name":
            print("%s Name: %s" % (name, get_text(child)))
        elif child.nodeName == "NumberOfSamples":
            print("%s NumberOfSamples: %s" % (name, get_text(child)))
        elif child.nodeName == "RawSignal":
            print("%s RawSignal: %s" % (name, ','.join(map(str, get_packed_values(child)))))
        elif child.nodeName == "ScriptStep":
            print("%s ScriptStep: %s" % (name, ','.join(map(str, get_packed_values(child)))))
        elif child.nodeName == "UnitX":
            print("%s UnitX: %s" % (name, get_text(child)))
        elif child.nodeName == "UnitY":
            print("%s UnitY: %s" % (name, get_text(child)))
        elif child.nodeName == "XMaxVisibleRange":
            print("%s XMaxVisibleRange: %s" % (name, get_text(child)))
        elif child.nodeName == "XMinVisibleRange":
            print("%s XMinVisibleRange: %s" % (name, get_text(child)))
        elif child.nodeName == "XStart":
            print("%s XStart: %s" % (name, get_text(child)))
        elif child.nodeName == "XStartAligned":
            print("%s XStartAligned: %s" % (name, get_text(child)))
        elif child.nodeName == "XStep":
            print("%s XStep: %s" % (name, get_text(child)))
        elif child.nodeName == "XStepAligned":
            print("%s XStepAligned: %s" % (name, get_text(child)))
        elif child.nodeName == "YMaxVisibleRange":
            print("%s YMaxVisibleRange: %s" % (name, get_text(child)))
        elif child.nodeName == "YMinVisibleRange":
            print("%s YMinVisibleRange: %s" % (name, get_text(child)))
        else:
            raise UnexpectedNodeError(child, "Unexpected node under SignalData element")


def handle_raw_signal_set(name, raw_signal_set):
    assert raw_signal_set.nodeName == name
    for child in raw_signal_set.childNodes:
        if child.nodeName == "Channel":
            handle_channel(name, child)
        elif child.nodeName == "Current":
            handle_current(name, child)
        elif child.nodeName == "HasData":
            print("%s HasData: %s" % (name, get_text(child)))
        elif child.nodeName == "SignalData":
            handle_signal_data(name, child)
        elif child.nodeName == "Voltage":
            handle_voltage(name, child)
        else:
            raise UnexpectedNodeError(child, "Unexpected node under %s element" % name)

def handle_raw_signals(raw_signals):
    assert raw_signals.nodeName == "RawSignals"
    for child in raw_signals.childNodes:
        handle_raw_signal_set(child.nodeName, child)

def handle_script(name, script):
    assert script.nodeName == "Script"
    for child in script.childNodes:
        if child.nodeName == "AllowEdit":
            print("%s Script AllowEdit: %s" % (name, get_text(child)))
        elif child.nodeName == "ScriptText":
            print("%s ScriptText: '%s'" % (name, bytes(get_packed_values(child)).decode('utf-16-le').replace('\r','\\r').replace('\n','\\n').replace('\'', '\\\'')))
        else:
            raise UnexpectedNodeError(child, "Unexpected node under %s Script element" % name)


def handle_chip(chip):
    assert chip.nodeName == "Chip"
    for child in chip.childNodes:
        if child.nodeName == "ID":
            print("Chip ID: %s" % (get_text(child)))
        elif child.nodeName == "AssayHeader":
            print("Chip AssayHeader: %s" % (child.toxml()))
        elif child.nodeName == "AssayBody":
            handle_assay_body(child)
        elif child.nodeName == "Script":
            handle_script("Chip", child)
        elif child.nodeName == "ChipInformation":
            print("ChipInformation: %s" % (child.toxml()))
        elif child.nodeName == "Instrument":
            print("Instrument: %s" % (child.toxml()))
        elif child.nodeName == "ComPortSettings":
            print("ComPortSettings: %s" % (child.toxml()))
        elif child.nodeName == "DataStatus":
            print("DataStatus: %s" % (child.toxml()))
        elif child.nodeName == "RawSignals":
            handle_raw_signals(child)
        elif child.nodeName == "Files":
            print("Files: %s" % (child.toxml()))
        elif child.nodeName == "Diagnostics":
            print("Diagnostics: %s" % (child.toxml()))
        elif child.nodeName == "Packet":
            print("Packet: %s" % (','.join(map(str, get_packed_values(child)))))
        elif child.nodeName == "Imported":
            print("Imported: %s" % (get_text(child)))
        elif child.nodeName == "HasData":
            print("HasData: %s" % (get_text(child)))
        elif child.nodeName == "NumberOfAcquiredSamples":
            print("NumberOfAcquiredSamples: %s" % (get_text(child)))
        elif child.nodeName == "PacketFileName":
            print("PacketFileName: %s" % (child.toxml()))
        else:
            raise UnexpectedNodeError(child, "Unexpected node under <Chip> element")

def handle_chips(chips):
    assert chips.nodeName == "Chips"
    for child in chips.childNodes:
        if child.nodeName == "Chip":
            handle_chip(child)
        else:
            raise UnexpectedNodeError(child, "Unexpected node under <Chips> element")

def handle_chipset(chipset):
    assert chipset.nodeName == "Chipset"
    for child in chipset.childNodes:
        if child.nodeName == "Method":
            print("Chipset Method: %s" % child.toxml())
        elif child.nodeName == "Chips":
            handle_chips(child)
        elif child.nodeName == "LogBook":
             print("Chipset LogBook: %s" % child.toxml())
        elif child.nodeName == "FileType":
            print("Chipset FileType: %s" % (get_text(child)))
        elif child.nodeName == "Type":
            print("Chipset Type: %s" % (get_text(child)))
        elif child.nodeName == "Class":
            print("Chipset Class: %s" % (get_text(child)))
        elif child.nodeName == "DataType":
            print("Chipset DataType: %s" % (get_text(child)))
        elif child.nodeName == "ExternalLinks":
            print("Chipset ExternalLinks: %s" % (get_text(child)))
        elif child.nodeName == "PersistSampleSignals":
            print("Chipset PersistSampleSignals: %s" % (get_text(child)))
        else:
            raise UnexpectedNodeError(child, "Unexpected node under <Chipset> element")

def parse_data_xml(data_xml):
    data = parseString(data_xml)
    data.normalize
    for node in data.childNodes:
        if node.nodeName == "Chipset":
            handle_chipset(node)
        else:
            raise UnexpectedNodeError(node, "Unexpected node in embedded Compressed Data XML document")

def inflate(data):
    decompress = zlib.decompressobj(
            -zlib.MAX_WBITS
    )
    inflated = decompress.decompress(data)
    inflated += decompress.flush()
    return inflated

def parse_xad_file(xad_file):
    xad = parse(xad_file)
    xad.normalize
    for child in xad.childNodes:
        if child.nodeName == "#comment":
            xad_handle_comment(child)
        elif child.nodeName == "compressed_data":
            text = get_text(child)
            m = re.match('.*?(.Oy9.*)$', text, flags=re.DOTALL)
            if not m:
                print("error in re")
                raise
            decoded = b64decode(text)
            decoded_header = decoded[0:76]
            handle_header(decoded_header)
            compressed_data = decoded[76:-9]
            decoded_footer = decoded[-9:]
            print("Have compressed_data decoded footer 0x%s" % (decoded_footer.hex()))
            data_xml = inflate(compressed_data).decode('utf-16-le')
            parse_data_xml(data_xml)
        else:
            raise UnexpectedNodeError(child, "Unexpected node in XAD XML document")

def main():
    parser = argparse.ArgumentParser(description='Convert a chip data file from Bioanalyzer 2100')
    parser.add_argument('xad', help='the input chip data (XAD) file')
    args = parser.parse_args()

    parse_xad_file(args.xad)

if __name__ == "__main__":
    main()
