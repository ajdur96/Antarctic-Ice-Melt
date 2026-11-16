"""Build index.html: embed Antarctica data.json and the DC module into template.html.
Usage: python 4_build_html.py"""
t = open("template.html").read()
t = t.replace("__DATA__", open("data.json").read()).replace("__DCMODULE__", open("dc/dc_module.js").read())
open("../index.html", "w").write(t)
