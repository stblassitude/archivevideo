#!/usr/bin/env python

import getopt
import json
import os
import re
import shutil
import string
import subprocess
import sys

from fractions import Fraction
from pipes import quote
from pprint import pprint
from string import Template


class Options:
	def __init__(self):
		self.dont = False
		self.downmix = False
		self.overwrite = False
		self.verbose = False
		self.x265 = True


def quoteArgs(args):
	"""
	Given a list of arguments suitable for subprocess.Popen(), returns
	a string that should be safe to use with os.system().
	"""
	return string.join(map(lambda a: quote(a), args))


class Object(object):
	pass


class Ratio:
	def __init__(self, s):
		s = re.sub(r'[xX/:]', '/', s)
		self.fraction = Fraction(s).limit_denominator(10000)
		self.numerator = self.fraction.numerator
		self.denominator = self.fraction.denominator
		self.int = int(float(self.fraction)+0.5)

	def __repl__(self):
		return repr(self.fraction)

class MediaMetadata:
	def __init__(self, file):
		p = subprocess.Popen(['ffprobe', '-v', 'quiet', '-print_format',
				'json', '-show_format', '-show_streams', file],
			stdout=subprocess.PIPE)
		self.info = json.load(p.stdout)
		self.filename = self.info['format']['filename']
		for stream in self.info['streams']:
			t = stream.get('codec_type')
			if t == "video":
				self.video = Object()
				self.video.codec = stream['codec_name']
				w = int(stream.get('coded_width', 0))
				if w == 0:
					w = stream.get('width')
				self.video.width = w
				h = int(stream.get('coded_height', 0))
				if h == 0:
					h = stream.get('height')
				self.video.height = h
				self.video.aspect = Ratio(stream.get('display_aspect_ratio', float(w)/h))
				self.video.pixel_aspect = Ratio(stream.get('sample_aspect_ratio', 1))
				self.video.interlaced = stream.get('field_order', '') != 'progressive'
				self.video.pi = 'i' if self.video.interlaced else 'p'
				self.video.rater = Ratio(stream.get('r_frame_rate'))
				self.video.rate = self.video.rater.int
				self.video.spec = "{video.height}{video.pi}{video.rate}".format(video=self.video)
			elif t == "audio":
				self.audio = Object()
				self.audio.codec = stream['codec_name']
				self.audio.channels = stream['channels']


def getInfo(f):
	global options
	info = MediaMetadata(f) 
	if options.verbose:
		pprint(info.info)
	
	print "info\t{info.filename}\t{info.video.codec}/{info.video.spec}\t{info.audio.codec},{info.audio.channels}".format(info=info)


def targetFilename(file):
	"""
	Compute the target filename based on the source filename.
	"""
	return re.sub(r'\.[a-zA-Z0-9]+$', '.mkv', file)


def ffmpegArgs(meta, tgt):
	global options
	
	args = [ "ffmpeg", "-i", meta.filename]
	args.extend(["-threads", "0"])
	args.extend(["-hide_banner"])
	if not options.verbose:
		args.extend(["-loglevel", "panic"])
	if options.overwrite:
		args.extend(['-y'])

	if meta.video.interlaced:
	   	args.extend(["-deinterlace"])

	# Set maximum size, and fix pixel aspect ratio to 1:1, if needed.
	h = meta.video.height
	w = meta.video.width
	if h > 720:
		h = 720
		w = int(h * meta.video.aspect.fraction)
	if meta.video.pixel_aspect.fraction != Fraction(1, 1):
		f = meta.video.pixel_aspect.fraction
		if f < 1.0:
			w = int(w * f)
		else:
			h = int(h / f)
	if h != meta.video.height or w != meta.video.width:
		args.extend(["-s", "{}x{}".format(w,h)])
		a = Fraction(w,h).limit_denominator(10000)
		args.extend(["-aspect", "{}:{}".format(a.numerator, a.denominator)])
	
	if options.x265:
		args.extend(["-vcodec", "libx265"])
		x265params = []
		if not options.verbose:
			x265params.extend(["log-level=error"])
		#x265params.extend(["crf=28"]) # crf=28 is the default
		if len(x265params) > 0:
			args.extend(["-x265-params", string.join(x265params, ",")])
	else:
		args.extend(["-vcodec", "libx264", "-tune", "film", "-profile", "main"])
		if meta.video.height < 720:
			args.extend(["-b:v", "1000k"])

	if options.downmix:
		args.extend(["-c:a", "libfdk_aac", "-ac", "2", "-ab", "96k"])
	else:
		#args.extend(["-c:a", "copy"])
		args.extend(["-c:a", "libfdk_aac", "-vbr", "2"])

	args.append(tgt)
	
	return args


def transcode(src):
	global options
	
	meta = MediaMetadata(src)
	tgt = targetFilename(src)
	if os.path.abspath(src) == os.path.abspath(tgt):
		print "error\t{}\ttarget is the same as source".format(src)
		return
	if os.path.isfile(tgt):
		if options.overwrite:
			os.remove(tgt)
		else:
			print "error\t{}\talready exists".format(tgt)
			return

	args = ffmpegArgs(meta, tgt)

	print "\t{}".format(quoteArgs(args))
	if not options.dont:
		try:
			subprocess.check_call(args)
			dup = os.path.join(os.path.dirname(tgt), "Duplicates")
			os.makedirs(dup)
			os.rename(src, os.path.join(dup, os.path.basename(src)))
		except Exception as e:
			os.remove(tgt)
			print "error\t{}\t{}".format(src, e)


class Usage(Exception):
	def __init__(self, msg):
		self.msg = msg;
	def __str__(self):
		return repr(self.msg)


def main(argv=None):
	global options
	options = Options()
	cmd = transcode
	if argv is None:
		argv = sys.argv
   	try:
   		flags = "24fhinv"
   		try:
			opts, args = getopt.getopt(argv[1:], flags, ["help"])
		except getopt.error, msg:
			raise Usage(msg)
		for (o, v) in opts:
			if o == "-h" or o == "--help":
				print >>sys.stderr, ("Usage: archivevideo [-{}] file...\n"
					"options:\n"
					"\t-2\tdownmix audio to stereo, default is to reencode all channels\n"
					"\t-4\tuse x264 instead of x265 to encode video\n"
					"\t-f\toverwrite existing output files\n"
					"\t-h\tthis help text\n"
					"\t-i\tprint info on input files, instead of transcoding them\n"
					"\t-n\tdon't run ffmpeg, just print what would be done\n"
					"\t-v\tverbose information on progress\n"
					"Given one or more input video files, re-encode them to Matroska files using\n"
					"relatively space-saving encoding parameters. The output file will be placed in\n"
					"the same directory as the input file, and the input file will be moved to a\n"
					"subdirectory \"Duplicates\" in the same directory as the input file.\n"
					"If an error occurs, a message will be printed for that file, and work will\n"
					"continue with the next file specified."
					).format(flags)
				return 0
			if o == "-2":
				options.downmix = True
			if o == "-4":
				options.x265 = True
			if o == "-f":
				options.overwrite = True
			if o == "-i":
				cmd = getInfo
			if o == "-n":
				options.dont = True
			if o == "-v":
				options.verbose = True
		if len(args) == 0:
			raise Usage("At least one file needs to be specified")
		for a in args:
			cmd(a)
		return 0
	except Usage, err:
		print >>sys.stderr, err.msg
		print >>sys.stderr, "Usage: archivevideo [-{}] file...".format(flags)
		print >>sys.stderr, "for help use --help"
		return 64
                                                                                             
if __name__ == "__main__":
	sys.exit(main())
