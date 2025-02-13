#!/bin/bash
pyinstaller --noconfirm --onefile --windowed \
  --add-data "templates:templates" \
  --name "ResimBot" \
  --osx-bundle-identifier "com.resimbot.app" \
  app.py 