import requests

def translate(text, source_lang, target_lang):
    url = "https://api.mymemory.translated.net/get"

    params = {
        "q": text,
        "langpair": f"{source_lang}|{target_lang}"
    }

    r = requests.get(url, params=params)
    data = r.json()

    if data["responseStatus"] == 200:
        return data["responseData"]["translatedText"]
    else:
        return "Error: " + str(data)


result = translate("Hello", "en", "ta")
print("Translated:", result)
