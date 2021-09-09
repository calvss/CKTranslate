# CKTranslate
Automated translation tool for CK3 localization files.

This project takes in CK3-formatted YAML localization files for any language and automatically translates it using Google's Cloud Translation API to any other language.

See [the CK3 wiki page](https://ck3.paradoxwikis.com/Localization) for formatting info.

In order to use this project, you need to follow the instructions in the Cloud Translate [setup page](https://cloud.google.com/translate/docs/setup).
Start a project and follow the instructions until you obtain an authentication key. This JSON file will be used to authenticate all requests.

## Dependencies:
 * google-cloud-translate (v2.0.1)

## Usage:
```
usage: main.py [-h] 
               [--language [{l_english,l_french,l_german,l_spanish,l_simp_chinese,l_russian,l_korean}]]
               [--verbose]
               [--output OUTPUT]
               key input [input ...]

Reads a CK3-formatted YAML file and Uses the Google Translate API to automatically translate strings

positional arguments:
  key                          Google Translate API key JSON file.
  input                        Input filename(s). Supports globbing.

optional arguments:
  -h, --help                   show this help message and exit
  --output OUTPUT, -o          OUTPUT Output directory.
  --language, -l [LANGUAGE]    Output language.
  --verbose, -v
  
  Acceptable languages are: [l_english, l_french, l_german, l_spanish, l_simp_chinese, l_russian, l_korean]
  ```
  
  ## Example usage:
  ```
  python main.py keyfile.json game\localization\english\*.yml --output game\localization\simp_chinese --language l_simp_chinese -v
  ```
