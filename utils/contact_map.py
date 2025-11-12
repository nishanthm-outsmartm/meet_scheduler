CONTACTS = {
    "nishanth": "nishanthmanikandhan@gmail.com",
    "teja": "tejagangumalla476@gmail.com",
    "anto":"antojonith28@gmail.com",
    "jayanth":"jayanthanbu1242@gmail.com"
}

def resolve_emails_from_names(names):
    return [CONTACTS[name] for name in names if name in CONTACTS]
