"""Step 4: embed data.json into template.html -> index.html
Usage: python 4_build_html.py"""
t = open("template.html").read()
open("../index.html", "w").write(t.replace("__DATA__", open("data.json").read()))
