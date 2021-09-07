import yaml
import re
import argparse
import glob
import sys
import os
import html
from google.cloud import translate_v2 as translate

# count characters for Google Translate Quota
totalCharacterCount = 0

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
        result.append(dict(Result, translatedText='phrase', input=phrase))
    return result


def translate_text(target, text, keyfile):
    translate_client = translate.Client.from_service_account_json(keyfile)

    print("Making request")
    # Text can also be a sequence of strings, in which case this method
    # will return a sequence of results for each text.
    result = translate_client.translate(text, target_language=target)

    # print(u"Text: {}".format(result["input"]))
    # print(u"Translation: {}".format(result["translatedText"]))
    # print(u"Detected language: {}".format(result["detectedSourceLanguage"]))
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
        match = re.fullmatch(r'^(.*)_(l_[a-z_]*)\.yml$', inputFileName)
        if match is not None:
            nameName = match.group(1)
            nameLanguage = match.group(2)

            verbosePrint('Got filename', nameName)
            verbosePrint('Got language', nameLanguage)
        else:
            # filename is malformed
            print("Filename is wrong format:", inputFile, file=sys.stderr)
            continue

        # load file, editing weird CK3 format
        # valid yaml is '  key: 0 "value"'
        # CK3 uses ' key:0 "value"'

        # also sometimes xxx:0 "string" is accidentally xxx:0"string"
        # use regex to add space
        with open(inputFile) as yamlFile:
            rawText = ""
            for lineNum, line in enumerate(yamlFile):
                if lineNum == 0:
                    rawText = rawText + line
                else:
                    line = re.sub(r'^ *(.+").*', r' \1', line)
                    rawText = rawText + re.sub(r':([0-9]) *"', r': \1 "', line)

            content = yaml.load(rawText, Loader=yaml.FullLoader)

        innerLanguage = [*content][0]  # dict key is the language
        if innerLanguage != nameLanguage:
            print("Filename language mismatch:", inputFile, file=sys.stderr)
            continue

        innerContent = content[innerLanguage]

        for key, string in innerContent.items():
            # take only characters in the string itself
            # e.g. string = '0 "I want this part"'
            # string [3:-1] = 'I want this part'

            string = re.sub(r' "$', r'"$', string)
            paradoxInt = string[0]
            innerText = string[3:-1]

            # ignore empty strings
            if innerText == '':
                continue

            # ignore strings that link to other strings
            if re.search(r'\$(.+?)\$', innerText) is not None:
                continue

            # ignore strings that have complex formatting
            # e.g. #bold Hello World! #! is accepted
            #      Hello #bold World! #! is rejected
            # i.e. regex match strings where:
            #      (#format is not at the beginning) OR (#! is not at the end)

            # this is because if we split the string, then translate separately,
            # the meaning can change
            # e.g. '你是 #bold 中國 #! 人嗎?' -> ['你是', '中國', '人嗎?']
            # not translated properly -> ['you are', 'china', 'person?']
            if re.search(r'(?=.*#)(?=((?!^)(#[^!]+? )|^(.(?!.*#!$))*$))', innerText) is not None:
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

            innerContent[key] = paradoxInt + ' "' + newText + '"'

        content[args.language] = innerContent
        del content[innerLanguage]

        # need to do some raw string editing since CK3 yaml format is weird
        # valid yaml is '  key: 0 "value"'
        # CK3 uses ' key:0 "value"'
        # width=infinite prevents yaml newline on long lines
        rawText = yaml.dump(content, allow_unicode=True, width=float("inf")).splitlines()
        rawText = [re.sub(r'^  (.*): ([0-9] )', r' \1:\2', line) for line in rawText]
        rawText = '\n'.join(rawText)

        newFileName = nameName + '_' + args.language + '.yml'
        # output depends on command line switch
        if args.output is not None:
            outputFile = os.path.join(args.output, newFileName)
        else:
            outputFile = os.path.join(inputDir, newFileName)

        # not sure if newline='\n' is necessary or Windows \r\n line endings
        # built in localization files use '\n' line endings so I assumed
        with open(outputFile, mode='w', newline='\n', encoding='utf_8_sig') as yamlFile:
            print(rawText, file=yamlFile)
    verbosePrint("Translated characters:", totalCharacterCount)

if __name__ == '__main__':
    main()
