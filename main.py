import re
import argparse
import glob
import sys
import os
import html
import time
from google.cloud import translate_v2 as translate

# count characters for Google Translate Quota
totalCharacterCount = 0

# Google Translate delay seconds
requestDelay = 0.1

# list of supported CK3 languages
languageKeys = {
    'l_english': 'en',
    'l_french': 'fr',
    'l_german': 'de',
    'l_spanish': 'es',
    'l_simp_chinese': 'zh-CN',
    'l_russian': 'ru',
    'l_korean': 'ko'
}


def translate_text_dummy(target, text, keyfile):
    global totalCharacterCount

    Result = {
        'input': '',
        'translatedText': '',
        'detectedSourceLanguage': ''
    }

    result = []
    for phrase in text:
        totalCharacterCount = totalCharacterCount + len(phrase)
        # result.append(dict(Result, translatedText='「'+phrase+'」', input=phrase))
        result.append(dict(Result, translatedText='&#39;phrase&#39;', input=phrase))
    return result


def translate_text(target, text, keyfile):
    # Text can also be a sequence of strings, in which case this method
    # will return a sequence of results for each text.
    global requestDelay
    translate_client = translate.Client.from_service_account_json(keyfile)

    print("Making request. Delay:", requestDelay)

    for attempt in range(10):
        try:
            time.sleep(requestDelay)
            result = translate_client.translate(text, target_language=target)
        except:
            requestDelay = requestDelay * 1.5
        else:
            break
    else:
        # we failed all the attempts - deal with the consequences.
        print("Google API request fail", file=sys.stderr)
    return result


def main():
    parser = argparse.ArgumentParser(description='Reads a CK3-formatted YAML file and Uses the Google Translate API to automatically translate strings')
    parser.add_argument('key', help='Google Translate API key JSON file.')
    parser.add_argument('input', nargs='+', help='Input filename(s). Supports globbing.')
    parser.add_argument('--output', '-o', help='Output directory.')
    parser.add_argument('--language', '-l', nargs='?', choices=languageKeys.keys(), default='l_english', const='l_english', help='Output language.')
    parser.add_argument('--verbose', '-v', action='store_true')

    args = parser.parse_args()

    # define print function if verbose flag is set, else it's None
    verbosePrint = print if args.verbose else lambda *a, **k: None

    for i in vars(args):
        verbosePrint(i, getattr(args, i))

    # hopefully cross-platform globs
    fileList = []
    for globString in args.input:
        fileList = fileList + glob.glob(globString)

    verbosePrint('Translating the following files:', fileList)
    verbosePrint('Using the following keyfile:', args.key)

    for inputFile in fileList:
        # split directory and filename
        inputDir, inputFileName = os.path.split(inputFile)
        # split input filename into (xxx)_(l_language).yml using regex
        match = re.match(r'^(.*)_(l_[a-z_]*)\.yml$', inputFileName)
        if match is not None:
            nameName = match.group(1)
            nameLanguage = match.group(2)

            verbosePrint('Got filename', nameName)
            verbosePrint('Got language', nameLanguage)
        else:
            # filename is malformed
            print("Filename is wrong format:", inputFile, file=sys.stderr)
            continue

        rawText = []
        with open(inputFile, encoding='utf_8_sig') as yamlFile:
            for line in yamlFile:
                rawText.append(line.rstrip())

        innerLanguage = rawText[0][:-1]  # first line is the language

        if innerLanguage != nameLanguage:
            print("Filename language mismatch:", inputFile, file=sys.stderr)
            print(innerLanguage, file=sys.stderr)
            print(nameLanguage, file=sys.stderr)
            continue
        else:
            rawText[0] = args.language + ':'

        translatedText = []
        for line in rawText:
            # use regex to take only characters in the string itself
            # e.g. ( key:0 )"(I want this part)"( # comment)
            match = re.match(r'(.+?)"([^"]+?)"?( *# .*)?$', line)

            if match is not None:
                key, innerText = match.group(1, 2)
            else:
                translatedText.append(line)
                continue

            # ignore empty strings
            if innerText == '':
                translatedText.append(line)
                continue

            # ignore strings that link to other strings
            if re.search(r'\$(.+?)\$', innerText) is not None:
                translatedText.append(line)
                continue

            # ignore strings that have complex formatting
            # e.g. #bold Hello World! #! is accepted
            #      Hello #bold World! #! is rejected
            # i.e. regex match strings where:
            #      (#format is not at the beginning) OR (#! is not at the end)

            # this is because if we split the string and translate separately,
            # the meaning can change
            # e.g. '你是 #bold 中國 #! 人嗎?' -> ['你是', '中國', '人嗎?']
            # not translated properly -> ['you are', 'china', 'person?']
            if re.search(r'(?=.*#)(?=((?!^)(#[^!]+? )|^(.(?!.*#!$))*$))', innerText) is not None:
                translatedText.append(line)
                continue

            # if string contains formatting, obtain the tags
            formatTag = None
            if innerText[0] == '#':
                # format tag is always the first word because we ignored
                # all strings that have complex formatting
                formatTag = innerText.split()[0]

                # extract the unformatted text, minus the end tag '#!'
                innerText = innerText[len(formatTag)+1:-2]

            # split text into phrases using \n, translate, and then rejoin
            newText = []
            for phrase in translate_text(target=languageKeys[args.language],
                                         text=innerText.split('\\n'),
                                         keyfile=args.key):
                newText.append(html.unescape(phrase['translatedText']))
            newText = '\\n'.join(newText)

            # restore formatting and yaml syntax
            if formatTag is not None:
                newText = formatTag + ' ' + newText + '#!'

            line = key + '"' + newText + '"'
            translatedText.append(line)

        newFileName = nameName + '_' + args.language + '.yml'

        # this can be 'None' depending on command line
        outputPath = args.output or ''
        verbosePrint("Saving file", os.path.join(outputPath, newFileName))
        outputFile = os.path.join(outputPath, newFileName)

        # not sure if newline='\n' is necessary or Windows \r\n line endings
        # built in localization files use '\n' line endings so I assumed
        with open(outputFile, mode='w', newline='\n', encoding='utf_8_sig') as yamlFile:
            for line in translatedText:
                print(line, end='\n', file=yamlFile)
    verbosePrint("Translated characters:", totalCharacterCount)


if __name__ == '__main__':
    main()
