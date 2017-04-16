# archivevideo
Re-encode hard-disk recorder videos for archiving, reducing their size.

This python script will take one or more video files and re-encode
them with suitable parameters, chosen based on the properties of the source
file.

## Requirements

You need Python 2.7 and ffmpeg.  ffmpeg must have support for x265 and the
Fraunhofer AAC codecs enabled.

## Usage

`archivevideo` [`-24fhinv`] `file`...

Given one or more input video files, re-encode them to Matroska files using
relatively space-saving encoding parameters. The output file will be placed in
the same directory as the input file, and the input file will be moved to a
subdirectory "Duplicates" in the same directory as the input file.
If an error occurs, a message will be printed for that file, and work will
continue with the next file specified.

### Options

* `-2` downmix audio to stereo; default is to reencode all audio channels
* `-4` use x264 instead of x265 to encode the video
* `-f` overwrite existing output files
* `-h` print help text
* `-i` print info on input files, instead of transcoding them
* `-n` don't run ffmpeg, just print what would be done
* `-v` verbose information on progress

## License

(c) 2017 Stefan Bethke, all rights reserved. See [LICENSE](LICENSE) for
the BSD 2-clause license details.
