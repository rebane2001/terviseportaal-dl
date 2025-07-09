import re
import os
import sys
import json
import time
import base64
import shutil
import requests
import urllib.parse

basepath_mappings = {
    "analuus": ["EXAMINATION_REPORT", False],
    "arengu-teatis": ["NOTICE", False],
    "haiglaravi": ["EPICRISIS", True],
    "kasvamise-teatis": ["NOTICE", False],
    "kiirabi": ["AMBULANCE_CARD", True],
    "labivaatus": ["NOTICE", False],
    "noustamine": ["NOTICE", False],
    "operatsioon": ["EPICRISIS", False],
    "saatekirja-vastus": ["EXAMINATION_REPORT", False],
    "uuringud": ["EXAMINATION_REPORT", False],
    "vaktsineerimine": ["IMMUNIZATION", True],
    "vastuvott": ["EPICRISIS", True],
}

def theme_to_basepath(entry):
    source = entry.get("source")
    theme = entry.get("theme")
    code = entry.get("code", {}).get("code")

    if theme == "AMBULANCE": return "kiirabi"
    if theme == "ANALYSIS": return "analuus"
    if theme == "IMMUNIZATION": return "vaktsineerimine"
    if theme == "OPERATION" and code in ["1", "2", "3"]: return "operatsioon"
    if theme == "HOSPITAL_TREATMENT" and code in ["1", "2", "94"]: return "haiglaravi"
    if theme == "DIAGNOSTIC_REPORTS":
        if code == "64":
            if source == "TIS":
                return "saatekirja-vastus"
            return "uuringud"
    if theme == "RECEPTION":
        if code == "15": return "noustamine"
        if code == "14": return "arengu-teatis"
        if code == "13": return "labivaatus"
        if code == "12": return "kasvamise-teatis"
        if code in ["2", "4"]: return "vastuvott"
    raise Exception(f"Couldn't find a match for theme '{theme}' with code '{code}'")

def entry_to_url(entry):
    basepath = theme_to_basepath(entry)
    document_type, needs_doctype = basepath_mappings.get(basepath)
    if not document_type:
        raise Exception(f"Couldn't get the document type for '{basepath}'")
    document_path = entry["id"]["root"] + "_" + entry["id"]["extension"]
    document_path_b64 = base64.b64encode(urllib.parse.quote(document_path).encode()).decode()
    document_url = f"https://minu.terviseportaal.ee/tervikdokument/tervise-ajalugu/{document_path_b64}?"
    if needs_doctype:
        document_url += f"docTypeCode={entry['code']['code']}&"
    document_url += f"type={document_type}"
    return document_url

def download_file(url, filename, cookies=[]):
    with requests.get(url, cookies=cookies, stream=True) as r:
        r.raw.decode_content = True
        with open(filename, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

def main():
    if (len(sys.argv) == 2):
        print("Using session cookie from argument")
        host_session = sys.argv[1]
    else:
        print("What is your __Host-SESSION cookie?")
        host_session = input("(format: f81d4fae-7dec-11d0-a765-00a0c91e6bf6)")
    cookies = {
        'COOKIE_CONSENT': 'TECHNICAL_SELECTED',
        '__Host-SESSION': host_session,
    }

    try:
        r = requests.get('https://minu.terviseportaal.ee/api/auth/current-user', cookies=cookies)
        current_user = r.json()
    except requests.exceptions.JSONDecodeError:
        print("Failed to fetch current user, is your session cookie correct?")
        return
    print(f"Hi, {current_user['firstName']}!")
    fn = f"terviseportaal_{current_user['idCode']}_{round(time.time())}"
    print(f"Downloading data into {fn}")
    os.mkdir(fn)
    with open(os.path.join(fn,"current_user.json"), "x") as f:
        f.write(r.text)
    r = requests.get('https://minu.terviseportaal.ee/api/health-history', cookies=cookies)
    with open(os.path.join(fn,"health_history.json"), "x") as f:
        f.write(r.text)
    health_history = r.json()
    for i,entry in enumerate(health_history["result"]):
        entry_url = entry_to_url(entry)
        short_code = entry['id']['extension'][-8:]
        filename = f"{entry.get('effectiveTime')}_{short_code}_{theme_to_basepath(entry)}_{entry.get('organizationName','NULL')}"
        if len(filename) > 200:
            filename = filename[:200]
        filename = re.sub(r"[^\w\-.]","",filename.replace(" ", "_")) + ".html"
        print(f"[{i+1}/{len(health_history["result"])}] {filename}")
        download_file(entry_url, os.path.join(fn,filename), cookies=cookies)
        entry["downloadedUrl"] = filename
    with open(os.path.join(fn,"data.js"), "x") as f:
        f.write(f"window.healthData = {json.dumps({"user": current_user, "history": health_history["result"]})};")
    shutil.copyfile('template.html', os.path.join(fn,"_index.html"))
    print("Done!")

if __name__ == '__main__':
    main()
