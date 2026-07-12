# Mogan integration notice

`paste-widget.scm` is copied from Mogan STEM (`MoganLab/mogan`) for the
Magic Paste integration prototype. Copyright remains with the Mogan STEM
authors. The copied file is licensed under GNU GPL v3 or later; see `LICENSE`.

Upstream: https://gitee.com/MoganLab/mogan

Local changes: none. The web adapter in `latex_pipeline.py` is an independent
Python implementation that exchanges LaTeX documents with the isolated GPL
component and does not link Mogan desktop libraries into the web server.
