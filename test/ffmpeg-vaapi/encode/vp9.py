###
### Copyright (C) 2018-2019 Intel Corporation
###
### SPDX-License-Identifier: BSD-3-Clause
###

from ....lib import *
from ..util import *

spec = load_test_spec("vp9", "encode", "8bit")

def check_output(output, rcmode, gop):

  # only I and IP mode supported by codec
  ipbmode = 0 if gop <= 1 else 1

  ipbmsgs = [
    "Using intra frames only",
    "Using intra and P-frames",
    "Using intra, P- and B-frames"
  ]
  rcmsgs = dict(
    cqp = "Using constant-quality mode|RC mode: CQP",
    cbr = "RC mode: CBR",
    vbr = "RC mode: VBR",
  )

  m = re.search("Using VAAPI profile VAProfileVP9Profile0 ([0-9]*)", output, re.MULTILINE)
  assert m is not None, "Possible incorrect profile used"

  m = re.search(rcmsgs[rcmode], output, re.MULTILINE)
  assert m is not None, "Possible incorrect RC mode used"

  m = re.search(ipbmsgs[ipbmode], output, re.MULTILINE)
  assert m is not None, "Possible incorrect IPB mode used"

def check_psnr(params):
  call(
    "ffmpeg -hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -v verbose"
    " -i {encoded} -pix_fmt {mformat} -f rawvideo -vsync passthrough"
    " -vframes {frames} -y {decoded}".format(**params))

  get_media().baseline.check_psnr(
    psnr = calculate_psnr(
      params["source"], params["decoded"],
      params["width"], params["height"],
      params["frames"], params["format"]),
    context = params.get("refctx", []),
  )

#-------------------------------------------------#
#---------------------- CQP ----------------------#
#-------------------------------------------------#
@slash.requires(have_ffmpeg)
@slash.requires(have_ffmpeg_vaapi_accel)
@slash.requires(have_ffmpeg_vp9_vaapi_encode)
@slash.parametrize(*gen_vp9_cqp_parameters(spec))
@platform_tags(VP9_ENCODE_8BIT_PLATFORMS)
def test_8bit_cqp(case, ipmode, qp, quality, refmode, looplvl, loopshp):
  params = spec[case].copy()

  params.update(
    ipmode = ipmode, qp = qp, quality = quality, looplvl = looplvl,
    gop = 30 if ipmode != 0 else 1, refmode = refmode,
    loopshp = loopshp, mformat = mapformat(params["format"]))

  if params["mformat"] is None:
    slash.skip_test("{format} format not supported".format(**params))

  if refmode != 0:
    slash.skip_test("only refmode == 0 is supported")

  params["encoded"] = get_media()._test_artifact(
    "{}-{ipmode}-{qp}-{quality}-{refmode}-{looplvl}-{loopshp}"
    ".ivf".format(case, **params))
  params["decoded"] = get_media()._test_artifact(
    "{}-{ipmode}-{qp}-{quality}-{refmode}-{looplvl}-{loopshp}-{width}x{height}-{format}"
    ".yuv".format(case, **params))

  slash.logger.notice("NOTICE: 'refmode' parameter unused (not supported by plugin)")
  slash.logger.notice("NOTICE: 'quality' parameter unused (not supported by plugin)")

  output = call(
    "ffmpeg -hwaccel vaapi -vaapi_device /dev/dri/renderD128 -v verbose"
    " -f rawvideo -pix_fmt {mformat} -s:v {width}x{height} -i {source}"
    " -vf 'format=nv12,hwupload' -c:v vp9_vaapi -g {gop} -global_quality {qp}"
    " -loop_filter_level {looplvl} -loop_filter_sharpness {loopshp}"
    " -vframes {frames} -y {encoded}".format(**params))

  check_output(output, "cqp", params["gop"])

  check_psnr(params)

#-------------------------------------------------#
#---------------------- CBR ----------------------#
#-------------------------------------------------#
@slash.requires(have_ffmpeg)
@slash.requires(have_ffmpeg_vaapi_accel)
@slash.requires(have_ffmpeg_vp9_vaapi_encode)
@slash.parametrize(*gen_vp9_cbr_parameters(spec))
@platform_tags(VP9_ENCODE_8BIT_PLATFORMS)
def test_8bit_cbr(case, gop, bitrate, fps, refmode, looplvl, loopshp):
  params = spec[case].copy()

  params.update(
    gop = gop, bitrate = bitrate, fps = fps, refmode = refmode,
    looplvl = looplvl, loopshp = loopshp, mformat = mapformat(params["format"]),
    frames = params.get("brframes", params["frames"]))

  if params["mformat"] is None:
    slash.skip_test("{format} format not supported".format(**params))

  if refmode != 0:
    slash.skip_test("only refmode == 0 is supported")

  params["encoded"] = get_media()._test_artifact(
    "{}-{gop}-{bitrate}-{fps}-{refmode}-{looplvl}-{loopshp}"
    ".ivf".format(case, **params))
  params["decoded"] = get_media()._test_artifact(
    "{}-{gop}-{bitrate}-{fps}-{refmode}-{looplvl}-{loopshp}"
    "-{width}x{height}-{format}"
    ".yuv".format(case, **params))

  slash.logger.notice("NOTICE: 'refmode' parameter unused (not supported by plugin)")

  output = call(
    "ffmpeg -hwaccel vaapi -vaapi_device /dev/dri/renderD128 -v verbose"
    " -f rawvideo -pix_fmt {mformat} -s:v {width}x{height} -r:v {fps}"
    " -i {source} -vf 'format=nv12,hwupload' -c:v vp9_vaapi -g {gop}"
    " -b:v {bitrate}k -maxrate {bitrate}k -loop_filter_level {looplvl}"
    " -loop_filter_sharpness {loopshp} -vframes {frames}"
    " -y {encoded}".format(**params))

  check_output(output, "cbr", gop)

  # calculate actual bitrate
  encsize = os.path.getsize(params["encoded"])
  bitrate_actual = encsize * 8 * params["fps"] / 1024.0 / params["frames"]
  bitrate_gap = abs(bitrate_actual - bitrate) / bitrate

  get_media()._set_test_details(
    size_encoded = encsize,
    bitrate_actual = "{:-.2f}".format(bitrate_actual),
    bitrate_gap = "{:.2%}".format(bitrate_gap))

  assert(bitrate_gap <= 0.10)

  check_psnr(params)

#-------------------------------------------------#
#---------------------- VBR ----------------------#
#-------------------------------------------------#
@slash.requires(have_ffmpeg)
@slash.requires(have_ffmpeg_vaapi_accel)
@slash.requires(have_ffmpeg_vp9_vaapi_encode)
@slash.parametrize(*gen_vp9_vbr_parameters(spec))
@platform_tags(VP9_ENCODE_8BIT_PLATFORMS)
def test_8bit_vbr(case, gop, bitrate, fps, refmode, quality, looplvl, loopshp):
  params = spec[case].copy()

  # target percentage 50%
  minrate = bitrate
  maxrate = bitrate * 2

  params.update(
    gop = gop, bitrate = bitrate, fps = fps, refmode = refmode,
    quality = quality, looplvl = looplvl, loopshp = loopshp, minrate = minrate,
    maxrate = maxrate, mformat = mapformat(params["format"]),
    frames = params.get("brframes", params["frames"]))

  if params["mformat"] is None:
    slash.skip_test("{format} format not supported".format(**params))

  if refmode != 0:
    slash.skip_test("only refmode == 0 is supported")

  params["encoded"] = get_media()._test_artifact(
    "{}-{gop}-{bitrate}-{fps}-{refmode}-{quality}-{looplvl}-{loopshp}"
    ".ivf".format(case, **params))
  params["decoded"] = get_media()._test_artifact(
    "{}-{gop}-{bitrate}-{fps}-{refmode}-{quality}-{looplvl}-{loopshp}"
    "-{width}x{height}-{format}"
    ".yuv".format(case, **params))

  slash.logger.notice("NOTICE: 'refmode' parameter unused (not supported by plugin)")
  slash.logger.notice("NOTICE: 'quality' parameter unused (not supported by plugin)")

  output = call(
    "ffmpeg -hwaccel vaapi -vaapi_device /dev/dri/renderD128 -v verbose"
    " -f rawvideo -pix_fmt {mformat} -s:v {width}x{height} -r:v {fps}"
    " -i {source} -vf 'format=nv12,hwupload' -c:v vp9_vaapi -g {gop}"
    " -b:v {minrate}k -maxrate {maxrate}k -loop_filter_level {looplvl}"
    " -loop_filter_sharpness {loopshp}"
    " -vframes {frames} -y {encoded}".format(**params))

  check_output(output, "vbr", gop)

  # calculate actual bitrate
  encsize = os.path.getsize(params["encoded"])
  bitrate_actual = encsize * 8 * params["fps"] / 1024.0 / params["frames"]

  get_media()._set_test_details(
    size_encoded = encsize,
    bitrate_actual = "{:-.2f}".format(bitrate_actual))

  # acceptable bitrate within 25% of minrate and 10% of maxrate
  assert(minrate * 0.75 <= bitrate_actual <= maxrate * 1.10)

  check_psnr(params)
