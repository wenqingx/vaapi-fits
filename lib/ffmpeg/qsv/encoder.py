###
### Copyright (C) 2018-2021 Intel Corporation
###
### SPDX-License-Identifier: BSD-3-Clause
###

import re
import slash
import random

from ....lib import platform
from ....lib.ffmpeg.encoderbase import BaseEncoderTest, Encoder as FFEncoder
from ....lib.ffmpeg.util import have_ffmpeg_hwaccel, have_ffmpeg_encoder, have_ffmpeg_decoder
from ....lib.ffmpeg.qsv.util import mapprofile, mapprofile_stringapi, using_compatible_driver, have_encode_main10sp
from ....lib.ffmpeg.qsv.decoder import Decoder
from ....lib.common import mapRangeInt, get_media, call, exe2os, timefn, filepath2os
from ....lib.codecs import Codec
from ....lib.formats import PixelFormat
from ....lib.string_api import *


class Encoder(FFEncoder):
  hwaccel   = property(lambda s: "qsv")
  tilecols  = property(lambda s: s.ifprop("tilecols", " -tile_cols {tilecols}"))
  tilerows  = property(lambda s: s.ifprop("tilerows", " -tile_rows {tilerows}"))
  ldb       = property(lambda s: s.ifprop("ldb", " -low_delay_brc {ldb}"))
  iqfactor  = property(lambda s: s.ifprop("iqfactor", " -i_qfactor {iqfactor}"))
  bqfactor  = property(lambda s: s.ifprop("bqfactor", " -b_qfactor {bqfactor}"))
  iqoffset  = property(lambda s: s.ifprop("iqoffset", " -i_qoffset {iqoffset}"))
  bqoffset  = property(lambda s: s.ifprop("bqoffset", " -b_qoffset {bqoffset}"))

  @property
  def hwupload(self):
    return f"{super().hwupload}=extra_hw_frames=120"

  @property
  def hwdevice(self):
    return f'qsv,child_device={get_media().render_device}'

  @property
  def qp(self):
    def inner(qp):
      if self.codec in [Codec.MPEG2]:
        mqp = mapRangeInt(qp, [0, 100], [1, 51])
        return f" -q {mqp}"
      if self.codec in [Codec.AV1] and "ICQ" == self.rcmode:
        mqp = mapRangeInt(qp, [0, 255], [1, 51])
        return f" -global_quality {mqp}"
      if self.codec in [Codec.HEVC] and "QVBR" == self.rcmode:
        mqp = mapRangeInt(qp, [0, 255], [1, 51])
        return f" -global_quality {mqp}"
      return f" -q {qp}"
    return self.ifprop("qp", inner)

  @property
  def quality(self):
    def inner(quality):
      if self.codec in [Codec.JPEG]:
        return f" -global_quality {quality}"
      return f" -preset {quality}"
    return self.ifprop("quality", inner)

  def map_profile_stringapi(self, codec, profile):
    return mapprofile_stringapi(codec, profile)

  @property
  def encparams(self):
    _enc_params_stringapi = vars(self).get("is_enc_params_stringapi", 0)
    if _enc_params_stringapi:
      return (f"{self.encparams_string_api}")
    else:
      return (
        f"{super().encparams}{self.ldb}"
        f"{self.iqfactor}{self.bqfactor}"
        f"{self.iqoffset}{self.bqoffset}"
      )

  @property
  def encparams_string_api(self):
    _encparams = ""
    if self.profile != None and len(self.profile.strip())>0:
        r,_,_profile=self.profile.partition('-profile:v')
        _profile=_profile.strip()
        _codec_profile = self.map_profile_stringapi(self.codec, _profile)
        if _codec_profile is None:
          slash.skip_test("profile is not supported".format(**vars(self)))
        _encparams = f"CodecProfile={_codec_profile}"
    if self.level != None and len(self.level.strip())>0:
        _level=re.findall("\d+", self.level)[0]
        _encparams = f"{_encparams}:CodecLevel={_level}"
    if self.rcmode != None and len(self.rcmode.strip())>0:
       _rc_mode=RateControlMethod.MFX_RATECONTROL_CQP.value
       if self.rcmode.upper() in ["CQP"]:
         _rc_mode=RateControlMethod.MFX_RATECONTROL_CQP.value
       elif self.rcmode.upper() in ["CBR"]:
         _rc_mode=RateControlMethod.MFX_RATECONTROL_CBR.value
       elif self.rcmode.upper() in ["VBR"]:
         _rc_mode=RateControlMethod.MFX_RATECONTROL_VBR.value
       elif self.rcmode.upper() in ["ICQ"]:
         _rc_mode=RateControlMethod.MFX_RATECONTROL_ICQ.value
       _encparams = f"{_encparams}:RateControlMethod={_rc_mode}"
    if self.qp != None and len(self.qp.strip())>0:
        _qp=re.findall("\d+", self.qp)[0]
        _rc_mode=RateControlMethod.MFX_RATECONTROL_CQP.value
        _encparams = f"{_encparams}:QPI={_qp}:QPP={_qp}:QPB={_qp}"
    if self.gop != None and len(self.gop.strip())>0:
        _gop=re.findall("\d+", self.gop)[0]
        _encparams = f"{_encparams}:GopPicSize={_gop}"
    if self.bframes != None and len(self.bframes.strip())>0:
        _bframes=re.findall("\d+", self.bframes)[0]
        _encparams = f"{_encparams}:GopRefDist={_bframes}"
    if self.slices != None and len(self.slices.strip())>0:
        _slices=re.findall("\d+", self.slices)[0]
        _encparams = f"{_encparams}:NumSlice={_slices}"
    if self.maxframesize != None and len(self.maxframesize.strip())>0:
        _maxframesize=re.findall("\d+", self.maxframesize)[0]
        _encparams = f"{_encparams}:MaxSliceSize={_maxframesize}"
    if self.minrate != None and len(self.minrate.strip())>0:
        _minrate=re.findall("\d+", self.minrate)[0]
        _encparams = f"{_encparams}:TargetKbps={_minrate}"
    if self.maxrate != None and len(self.maxrate.strip())>0:
        _maxrate=re.findall("\d+", self.maxrate)[0]
        _encparams = f"{_encparams}:MaxKbps={_maxrate}"
    if self.refs != None and len(self.refs.strip())>0:
        _refs=re.findall("\d+", self.refs)[0]
        _encparams = f"{_encparams}:NumRefFrame={_refs}"
    if self.ladepth != None and len(self.ladepth.strip())>0:
        _ladepth=re.findall("\d+", self.ladepth)[0]
        _encparams = f"{_encparams}:LookAheadDepth={ladepth}"
    if self.intref != None and len(self.intref.strip())>0:
        # for exampe: self.intref="  -int_ref_type 1 -int_ref_cycle_size 4 -int_ref_cycle_dist 20"
        # to get intref_type
        r,_,_intref_type=self.intref.partition('-int_ref_type')
        _intref_type,_,r=_intref_type.partition('-int_ref_cycle_size')
        # to get intref_size
        _intref_type=_intref_type.strip()
        r,_,_intref_size=self.intref.partition('-int_ref_cycle_size')
        _intref_size,_,r=_intref_size.partition('-int_ref_cycle_dist')
        _intref_size=_intref_size.strip()
        # to get intref_dist
        r,_,_intref_refdist=self.intref.partition('-int_ref_cycle_dist')
        _intref_refdist=_intref_refdist.strip()
        _encparams = f"{_encparams}:mfxExtCodingOption2.IntRefType={_intref_type}:mfxExtCodingOption2.IntRefCycleSize={_intref_size}:mfxExtCodingOption3.IntRefCycleDist={_intref_refdist}"
    if self.extbrc != None and len(self.extbrc.strip())>0:
        _extbrc=re.findall("\d+", self.extbrc)[0]
        _encparams = f"{_encparams}:ExtBRC={_extbrc}"
    if self.ldb != None and len(self.ldb.strip())>0:
        _ldb=re.findall("\d+", self.ldb)[0]
        _encparams = f"{_encparams}:mfxExtCodingOption3.LowDelayBRC={_ldb}"
    if self.tilecols != None and len(self.tilecols.strip())>0:
        _tilecols=re.findall("\d+", self.tilecols)[0]
        _encparams = f"{_encparams}:mfxExtAV1TileParam.NumTileColumns={_tilecols}"
    if self.tilerows != None and len(self.tilerows.strip())>0:
        _tilerows=re.findall("\d+", self.tilerows)[0]
        _encparams = f"{_encparams}:mfxExtAV1TileParam.NumTileRows={_tilerows}"
    if self.strict != None and len(self.strict.strip())>0:
        _strict=re.findall("\d+", self.strict)[0]
        _encparams = f"{_encparams}:GopOptFlag={_strict}"
    if self.pict != None and len(self.pict.strip())>0:
        _pict=re.findall("\d+", self.pict)[0]
        _encparams = f"{_encparams}:mfxExtCodingOption.PicTimingSEI={_pict}"
    if self.quality != None and len(self.quality.strip())>0:
        _quality=re.findall("\d+", self.quality)[0]
        _encparams = f"{_encparams}:TargetUsage={_quality}"
    if self.lowpower != None and len(self.lowpower.strip())>0:
        _lowpower=re.findall("\d+", self.lowpower)[0]
        _encparams = f"{_encparams}:LowPower={_lowpower}"
    #{self.forced_idr} ffmpeg
    #{self.pict}{self.rqp}

    if _encparams != None and len(_encparams.strip()) > 1:
        if ':' == _encparams[0]:
            _encparams = _encparams[1:]
    return f"{_encparams}"

  @timefn("ffmpeg:encode")
  def encode(self):
    if vars(self).get("_encoded", None) is not None:
      get_media().artifacts.purge(self._encoded)
    self._encoded = get_media().artifacts.reserve(self.encoded_ext)

    _enc_params_stringapi = 0
    _stringapi_param = 0
    _cmdline_stringapi_param = get_media().stringapi #passed through from the test cases cmdline option
    if _cmdline_stringapi_param == 1: #to call encparams_string_api
      _stringapi_param = 1
    elif _cmdline_stringapi_param == 2: #the random is even, then to call encparams_string_api
      _randint = random.randint(1,10)
      if _randint%2==0: #even
        _stringapi_param = 1
      else:
        _stringapi_param = 0
    else:
      _enc_params_stringapi = 0

    #  check whether call encparams_string_api
    _enc_params_stringapi = all([
      get_media()._get_platform_stringapi_enable(), #the platform whether support stringapi
      _stringapi_param == 1
    ])

    if _enc_params_stringapi == True:
      vars(self).update(is_enc_params_stringapi=1)
      return call(
        f"{exe2os('ffmpeg')} -v verbose {self.hwinit}"
        f" -f rawvideo -pix_fmt {self.format} -s:v {self.width}x{self.height}"
        f" {self.fps} -i {self.ossource}"
        f" -vf 'format={self.hwformat}{self.hwupload}{self.roi}'"
        f" -an -c:v {self.ffencoder} -qsv_params '{self.encparams}'"
        f" -vframes {self.frames} -y {self.ffoutput}"
      )
    else:
      vars(self).update(is_enc_params_stringapi=0)
      return call(
        f"{exe2os('ffmpeg')} -v verbose {self.hwinit}"
        f" -f rawvideo -pix_fmt {self.format} -s:v {self.width}x{self.height}"
        f" {self.fps} -i {self.ossource}"
        f" -vf 'format={self.hwformat}{self.hwupload}{self.roi}'"
        f" -an -c:v {self.ffencoder} {self.encparams}"
        f" -vframes {self.frames} -y {self.ffoutput}"
      )

@slash.requires(*have_ffmpeg_hwaccel("qsv"))
@slash.requires(using_compatible_driver)
class EncoderTest(BaseEncoderTest):
  EncoderClass = Encoder
  DecoderClass = Decoder

  def map_profile(self):
    return mapprofile(self.codec, self.profile)

  def validate_caps(self):
    if vars(self).get("profile", None) in ["main10sp"] and not have_encode_main10sp(self.ffencoder):
      slash.skip_test(f"{self.ffencoder} main10sp not supported")

    # FIXME: this should go into BaseEncoderTest
    if self.rcmode in ["cbr", "vbr"]:
      # brframes, if specified, overrides "frames" for bitrate control modes
      self.frames = vars(self).get("brframes", self.frames)

    super().validate_caps()

  def check_metrics(self):
    # TCBRC check
    is_tcbrc = all([
      self.rcmode in ["vbr"],
      vars(self).get("lowpower", 0),
      vars(self).get("ldb", 0),
      vars(self).get("strict", 0) == -1,
    ])

    if is_tcbrc:
      output = call(
        f"{exe2os('ffprobe')} -i {self.encoder.osencoded}"
        f" -show_entries frame=pkt_size,pict_type -of compact"
      )

      actual = re.findall(r'(?<=pkt_size=).[0-9]*(?=\|pict_type=[IPB])', output)
      assert len(actual) == self.frames, "Probe failed for frame pkt_size"

      target = self.bitrate * 1000 / 8 / self.fps # target bytes per frame
      results = [int(frmsize) < target * 1.2 for frmsize in actual]
      failed = results.count(False)
      rate = failed / len(results)

      get_media()._set_test_details(**{
        "tcbrc:frame:target (bytes)" : f"{target:0.2f}",
        "tcbrc:frame:fails" : f"{failed} ({rate:0.2%})",
      })

      assert rate < 0.2, "Too many TCBRC frames exceed target frame size"

    super().check_metrics()

  def check_output(self):
    # init
    m = re.search("Initialize MFX session", self.output, re.MULTILINE)
    assert m is not None, "It appears that the QSV plugin did not load"

    # rate control mode
    if self.codec not in [Codec.JPEG]:
      mode = "LA" if vars(self).get("ladepth", None) is not None else self.rcmode
      m = re.search(f"RateControlMethod: {mode.upper()}", self.output, re.MULTILINE)
      assert m is not None, "Possible incorrect RC mode used"

    # lowpower
    if self.codec not in [Codec.JPEG, Codec.MPEG2]:
      if get_media()._get_gpu_gen() < 13:
         vdenc = "ON" if vars(self).get("lowpower", 0) else "OFF"
      else:
         vdenc = "OFF" if vars(self).get("lowpower", 0) else "ON"
      m = re.search(f"VDENC: {vdenc}", self.output, re.MULTILINE)
      assert m is not None, "Possible incorrect VDENC/VME mode used"

    # fps
    if vars(self).get("fps", None) is not None:
      m = re.search(f"FrameRateExtD: 1; FrameRateExtN: {self.fps}", self.output, re.MULTILINE)
      assert m is not None, "Possible incorrect FPS used"

    # slices
    if vars(self).get("slices", None) is not None and self.codec not in [Codec.VP9]:
      m = re.search(f"NumSlice: {self.slices};", self.output, re.MULTILINE)
      assert m is not None, "Possible incorrect slices used"

    # ladepth
    if vars(self).get("ladepth", None) is not None:
      m = re.search(f"LookAheadDepth: {self.ladepth}", self.output, re.MULTILINE)
      assert m is not None, "The lookahead depth does not match test parameter"

    # main10sp
    if vars(self).get("profile", None) in ["main10sp"]:
      m = re.search(r"Main10sp.*: enable", self.output, re.MULTILINE)
      assert m is not None, "It appears that main10sp did not get enabled"

    # intref
    if vars(self).get("intref", None) is not None:
      patterns = [
        f"IntRefType: {self.intref['type']};"
        f"|IntRefType, value: {self.intref['type']}",
        f"IntRefCycleSize: {self.intref['size']};",
        f"IntRefCycleDist: {self.intref['dist']}",
      ]

      for pattern in patterns:
        m = re.search(pattern, self.output, re.MULTILINE)
        assert m is not None, f"'{pattern}' missing in output"

    # Max/min qp
    if vars(self).get("rqp", None) is not None:
      patterns = [
        f"MinQPI: {self.rqp['MinQPI']};",
        f"MaxQPI: {self.rqp['MaxQPI']};",
        f"MinQPP: {self.rqp['MinQPP']};",
        f"MaxQPP: {self.rqp['MaxQPP']};",
        f"MinQPB: {self.rqp['MinQPB']};",
        f"MaxQPB: {self.rqp['MaxQPB']}",
      ]

      for pattern in patterns:
        m = re.search(pattern, self.output, re.MULTILINE)
        assert m is not None, f"'{pattern}' missing in output"

def codec_test_class(codec, engine, bitdepth, **kwargs):
  # lowpower setting for codecs that support it
  if codec not in [Codec.JPEG, Codec.MPEG2]:
    kwargs.update(lowpower = 1 if engine == "vdenc" else 0)

  # caps lookup translation
  capcodec = codec
  if codec in [Codec.HEVC, Codec.VP9, Codec.AV1]:
    capcodec = f"{codec}_{bitdepth}"

  # ffmpeg plugin codec translation
  ffcodec = {
    Codec.AVC   : "h264",
    Codec.JPEG  : "mjpeg",
  }.get(codec, codec)

  @slash.requires(*have_ffmpeg_encoder(f"{ffcodec}_qsv"))
  @slash.requires(*have_ffmpeg_decoder(f"{ffcodec}_qsv"))
  @slash.requires(*platform.have_caps(engine, capcodec))
  class CodecEncoderTest(EncoderTest):
    def before(self):
      super().before()
      vars(self).update(
        caps = platform.get_caps(engine, capcodec),
        codec = codec,
        ffencoder = f"{ffcodec}_qsv",
        ffdecoder = f"{ffcodec}_qsv",
        **kwargs,
      )

    def validate_caps(self):
      assert PixelFormat(self.format).bitdepth == bitdepth
      super().validate_caps()

    def get_file_ext(self):
      return {
        Codec.AVC   : "h264",
        Codec.HEVC  : "h265",
        Codec.JPEG  : "mjpeg" if self.frames > 1 else "jpg",
        Codec.MPEG2 : "m2v",
        Codec.VP9   : "ivf",
        Codec.AV1   : "ivf",
      }[codec]

  return CodecEncoderTest

##### AVC #####
AVCEncoderTest      = codec_test_class(Codec.AVC, "encode", 8)
AVCEncoderLPTest    = codec_test_class(Codec.AVC,  "vdenc", 8)

##### HEVC #####
HEVC8EncoderTest    = codec_test_class(Codec.HEVC, "encode",  8)
HEVC8EncoderLPTest  = codec_test_class(Codec.HEVC,  "vdenc",  8)
HEVC10EncoderTest   = codec_test_class(Codec.HEVC, "encode", 10)
HEVC10EncoderLPTest = codec_test_class(Codec.HEVC,  "vdenc", 10)
HEVC12EncoderTest   = codec_test_class(Codec.HEVC, "encode", 12)

##### AV1 #####
AV1EncoderTest      = codec_test_class(Codec.AV1, "encode",  8)
AV1EncoderLPTest    = codec_test_class(Codec.AV1,  "vdenc",  8)
AV110EncoderTest    = codec_test_class(Codec.AV1, "encode", 10)
AV110EncoderLPTest  = codec_test_class(Codec.AV1,  "vdenc", 10)

##### VP9 #####
VP9_8EncoderTest    = codec_test_class(Codec.VP9, "encode",  8)
VP9_8EncoderLPTest  = codec_test_class(Codec.VP9,  "vdenc",  8)
VP9_10EncoderTest   = codec_test_class(Codec.VP9, "encode", 10)
VP9_10EncoderLPTest = codec_test_class(Codec.VP9,  "vdenc", 10)

##### JPEG/MJPEG #####
JPEGEncoderTest     = codec_test_class(Codec.JPEG, "vdenc", 8)

##### MPEG2 #####
MPEG2EncoderTest    = codec_test_class(Codec.MPEG2, "encode", 8)
