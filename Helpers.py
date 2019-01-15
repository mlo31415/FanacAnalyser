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
                        "fanzine" : "issue",
                        "mo." : "month",
                        "quartermonth" : "month",
                        "quarter" : "month",
                        "season" : "month",
                        "notes" : "notes",
                        "no." : "number",
                        "no,": "number",
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
        Log("***Error: no terminating '>' found in "+strlower+"'", True)
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
# Print the text to a log file open by the main program
# If isError is set also print it to the error file.
def Log(text, isError=False):
    global g_logFile
    global g_errorFile
    global g_logFanzine
    global g_newLogFanzine

    logtitle=None
    if g_newLogFanzine:
        logtitle=g_logFanzine

    if logtitle is not None:
        print(logtitle)
        print("\n"+logtitle, file=g_logFile)

    print(text)
    print(text, file=g_logFile)

    if isError:
        if logtitle is not None:
            print("----\n"+logtitle, file=g_errorFile)
        print(text, file=g_errorFile)


def LogSetFanzine(name):
    global g_logFanzine
    global g_lastLogFanzine
    global g_newLogFanzine
    g_newLogFanzine=g_lastLogFanzine is None or g_lastLogFanzine != name
    g_logFanzine=name
    g_lastLogFanzine=g_logFanzine


def LogOpen(logfilename, errorfilename):
    global g_logFile
    g_logFile=open(logfilename, "w+")

    global g_errorFile
    g_errorFile=open(errorfilename, "w+")

    global g_logFanzine
    g_logFanzine=None
    global g_lastLogFanzine
    g_lastLogFanzine=None
    global g_newLogFanzine
    g_newLogFanzine=True

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



# =============================================================================
# Check to see if an argument (int, float or string) is a number
def IsNumeric(arg):
    if type(arg) in [float, int]:
        return True

    try:
        x=float(arg)    # We throw away the result -- all we're interested in is if the conversation can be done without throwing an error
        return True
    except:
        return False



# =============================================================================
# Read a list of lines in from a file
# Strip leading and trailing whitespace and ignore lines which begin with a '#'
def ReadList(filename):
    if not os.path.exists(filename):
        print("ReadList can't open "+filename)
        return None
    f=open(filename, "r")
    list=f.readlines()
    f.close()

    list=[l.strip() for l in list]  # Strip leading and trailing whitespace
    list=[l for l in list if len(l)>0 and l[0]!= "#"]   # Drop empty lines and lines starting with "#"

    list=[l for l in list if l.find(" #") == -1] + [l[:l.find(" #")].strip() for l in list if l.find(" #") > 0]    # (all members not containing " #") +(the rest with the trailing # stripped)

    return list