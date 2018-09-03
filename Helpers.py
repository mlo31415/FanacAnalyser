import os
from bs4 import NavigableString
import urllib


#-------------------------------------------------------------
def CannonicizeColumnHeaders(header):
    # 2nd item is the cannonical form
    translationTable={
                        "published" : "date",
                        "editors" : "editor",
                        "zine" : "issue",
                        "mo." : "month",
                        "quartermonth" : "month",
                        "quarter" : "month",
                        "season" : "month",
                        "notes" : "notes",
                        "no." : "number",
                        "num" : "number",
                        "#" : "number",
                        "page" : "pages",
                        "pages" : "pages",
                        "pp," : "pages",
                        "pub" : "publisher",
                        "vol" : "volume",
                        "volume" : "volume",
                        "volumenumber" : "volnum",
                        "vol#" : "volnum",
                        "vol.#" : "volnum",
                        "wholenum" : "whole",
                        "year" : "year",
                      }
    try:
        return translationTable[header.replace(" ", "").replace("/", "").lower()]
    except:
        return header.lower()


#-----------------------------------------
# Find text bracketed by <b>...</b>
# Return the contents of the first pair of brackets found and the remainder of the input string
def FindBracketedText(s, b):
    strlower=s.lower()
    l1=strlower.find("<"+b.lower())
    if l1 == -1:
        return "", ""
    l1=strlower.find(">", l1)
    if l1 == -1:
        print("***Error: no terminating '>' found in "+strlower+"'")
        return "", ""
    l2=strlower.find("</"+b.lower()+">", l1+1)
    if l2 == -1:
        return "", ""
    return s[l1+1:l2], s[l2+3+len(b):]


#=====================================================================================
# Function to pull and href and accompanying text from a Tag
# The structure is "<a href='URL'>LINKTEXT</a>
# We want to extract the URL and LINKTEXT
def GetHrefAndTextFromTag(tag):
    try:
        href=tag.contents[0].attrs.get("href", None)
    except:
        try:
            href=tag.attrs.get("href")
        except:
            return tag, None

    return (tag.contents[0].string, href)


#=====================================================================================
# Remove certain strings which amount to whitespace
def RemoveHTMLDebris(str):
    return str.replace("<br>", "").replace("<BR>", "")


#=====================================================================================
# Function to generate the proper kind of path.  (This may change depending on the target location of the output.)
def RelPathToURL(relPath):
    if relPath == None:
        return None
    if relPath.startswith("http"):  # We don't want to mess with foreign URLs
        return None
    return "http://www.fanac.org/"+os.path.normpath(os.path.join("fanzines", relPath)).replace("\\", "/")


#=====================================================================================
# Simple function to name tags for debugging purposes
def N(tag):
    try:
        return tag.__class__.__name__
    except:
        return "Something"


#=====================================================================================
# Function to compress newline elements from a list of Tags.
def RemoveNewlineRows(tags):
    compressedTags = []
    for row in tags:
        if not isinstance(row, NavigableString):
            compressedTags.append(row)
    return compressedTags


#=====================================================================================
# Function to find the index of a string in a list of strings
def FindIndexOfStringInList(list, str):
    for i in range(0, len(list) - 1):
        if list[i] == str:
            return i


#=====================================================================================
# Function to attempt to decode an issue designation into a volume and number
# Return a tuple of Volume and Number
# If there's no volume specified, Volume is None and Number is the whole number
# If we can't make sense of it, return (None, None), so if the 2nd member of the tuple is None, conversion failed.
def DecodeIssueDesignation(str):
    try:
        return (None, int(str))
    except:
        i=0  # A dummy statement since all we want to do with an exception is move on to the next option.

    # Ok, it's not a simple number.  Drop leading and trailing spaces and see if it of the form #nn
    s=str.strip().lower()
    if len(s) == 0:
        return (None, None)
    if s[0] == "#":
        s=s[1:]
        if len(s) == 0:
            return (None, None)
        try:
            return (None, int(s))
        except:
            i=0 # A dummy statement since all we want to do with an exception is move on to the next option.

    # This exhausts the single number possibilities
    # Maybe it's of the form Vnn, #nn (or Vnn.nn or Vnn,#nn)

    # Strip any leading 'v'
    if len(s) == 0:
        return (None, None)
    if s[0] == "v":
        s=s[1:]
        if len(s) == 0:
            return (None, None)

    # The first step is to see if there's at least one of the characters ' ', '.', and '#' in the middle
    # We split the string in two by a span of " .#"
    # Walk through the string until we;ve passed the first span of digits.  Then look for a span of " .#". The look for at least one more digit.
    # Since we've dropped any leading 'v', we kno we must be of the form nn< .#>nnn
    # So if the first character is not a digit, we give up.
    if not s[0].isdigit():
        return (None, None)

    # Now, the only legetimate charcater other than digits are the three delimiters, so translate them all to blanks and then split into the two digit strings
    spl=s.replace(".", " ").replace("#", " ").split()
    if len(spl) != 2:
        return (None, None)
    try:
        return (int(spl[0]), int(spl[1]))
    except:
        return (None, None)


#=====================================================================================
# Function to search recursively for the table containing the fanzines listing
# flags is a dictionary of attributes and values to be matched, e.g., {"class" : "indextable", ...}
# We must match all of them
def LookForTable(soup, flags):

    tables=soup.find_all("table")
    for table in tables:
        ok=True
        for key in flags.keys():
            if key not in table.attrs or table.attrs[key]== None or table.attrs[key] != flags[key]:
                ok=False
                break
        if ok:
            return table
    return None


#==================================================================================
def CreateFanacOrgAbsolutePath(fanacDir, str):
    return "http://www.fanac.org/fanzines/"+fanacDir+"/"+str


#==================================================================================
# Return a properly formatted link
def FormatLink(name, url):
    # TODO: Do we need to deal with turning blanks into %20 whatsits?
    return '<a href='+url+'>'+name+'</a>'


#==================================================================================
# Create a name for comparison purposes which is lower case and without whitespace or punctuation
# We make it all lower case
# We move leading "The ", "A " and "An " to the rear
# We remove spaces and certain punctuation
def CompressName(name):
    name=name.lower()
    if name.startswith("the "):
        name=name[:4]+"the"
    if name.startswith("a "):
        name=name[:2]+"a"
    if name.startswith("an "):
        name=name[:3]+"an"
    return name.replace(" ", "").replace(",", "").replace("-", "").replace("'", "").replace(".", "").replace("’", "")


#==================================================================================
def CompareCompressedName(n1, n2):
    return CompressName(n1) == CompressName(n2)



#=============================================================================
# Format the Vol/Num/Whole information
def FormatSerial(vol, num, whole):
    if whole is not None and whole != 0 and vol is not None and vol !=0 and num is not None and num != 0:
        return "#"+str(whole)+"  (V"+str(vol)+"#"+str(num)+")"

    if whole is not None and whole != 0:
        return "#"+str(whole)

    v="?"
    n="?"
    if vol is not None and vol!=0:
        v=str(vol)
    if num is not None and num!=0:
        n=str(num)

    return "V"+v+"#"+n


#=============================================================================
# Print the text to a log file open by the main program
# If isError is set also print it to the error file.
def Log(text, isError=False):
    global g_logFile
    global g_errorFile

    print(text)
    print(text, file=g_logFile)

    if isError:
        print(text, file=g_errorFile)

def LogOpen(logfilename, errorfilename):
    global g_logFile
    g_logFile=open(logfilename, "w+")
    global g_errorFile
    g_errorFile=open(errorfilename, "w+")

def LogClose():
    global g_logFile
    g_logFile.close()
    global g_errorFile
    g_errorFile.close()

# =============================================================================
#   Change the filename in a URL
def ChangeFileInURL(url, newFileName):
    u=urllib.parse.urlparse(url)
    p=u[2].split("/")   # Split the path (which may include a filename) into components
    f=p[-1:][0].split(".")     # Split the last component of the path (which may be a filename) into stuff plus an extension
    if len(f) > 1:
        # If there is an extension, then the last compoent of the path is a filename to be replaced.
        p="/".join(p[:-1])+"/"+newFileName
    else:
        # Otherwise, we just tack on the new filename
        p="/".join(p)+"/"+newFileName

    u=(u[0], u[1], p, u[3], u[4], u[5])
    return urllib.parse.urlunparse(u)