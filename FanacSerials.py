from dataclasses import dataclass, field
import roman
import Helpers
import re

@dataclass()
class FanacSerial:
    Vol: int = None
    Num: int = None
    Whole: int = None
    Suffix: str = None

    #=============================================================================================
    # Try to interpret a complex string as serial information
    # If there's a trailing Vol+Num designation at the end of a string, interpret it.

    # We accept:
    #       ...Vnn[,][ ]#nnn[ ]
    #       ...nnn nnn/nnn      a number followed by a fraction
    #       ...nnn/nnn[  ]      vol/num
    #       ...rrr/nnn          vol (in Roman numerals)/num
    #       ...nn.mm
    #       ...nn[ ]

    def InterpretSerial(self, s):

        self.Vol=None
        self.Num=None
        self.Whole=None
        self.Suffix=None

        s=s.upper()

        # First look for a Vol+Num designation: Vnnn #mmm
        p=re.compile("^.*"+    # Leading stuff
                    "V([0-9]+),?\s*"+  # Vnnn + optional comma + optional whitespace
                    "#([0-9]+)([a-zA-Z]?)" #     # #nnn + optional single alphabetic character suffix
                    "\s*$")    # optional whitespace
        m=p.match(s)
        if m is not None and len(m.groups()) in [2, 3]:
            self.Vol=int(m.groups()[0])
            self.Num=int(m.groups()[1])
            if len(m.groups()) == 3:
                self.Suffix=m.groups()[2]
            return self

        p=re.compile("^.*"+    # Leading stuff
                    "V[oO][lL]\s*([0-9]+),?\s*"+  # Vol (or VOL) + optional space + nnn + optional comma + optional space
                    "#([0-9]+)([a-zA-Z]?)" #     + #nnn + optional single alphabetic character suffix
                    "\s*$")    # optional whitespace
        m=p.match(s)
        if m is not None and len(m.groups()) in [2, 3]:
            self.Vol=int(m.groups()[0])
            self.Num=int(m.groups()[1])
            if len(m.groups()) == 3:
                self.Suffix=m.groups()[2]
            return self

        # Now look for nnn nnn/nnn (fractions!)
        p=re.compile("^.*?([0-9]+)\s+([0-9]+)/([0-9]+)\s*$")    # Leading stuff + nnn + mandatory whitespace + nnn + slash + nnn * optional whitespace
        m=p.match(s)
        if m is not None and len(m.groups()) == 3:
            self.Whole=int(m.groups()[0]) +  int(m.groups()[1])/int(m.groups()[2])
            return self

        # Now look for nnn/nnn (which is understood as vol/num
        p=re.compile("^.*?([0-9]+)/([0-9]+)\s*$")    # Leading stuff + nnn + slash + nnn * optional whitespace
        m=p.match(s)
        if m is not None and len(m.groups()) == 2:
            self.Vol=int(m.groups()[0])
            self.Num=int(m.groups()[1])
            return self

        # Now look for xxx/nnn, where xxx is in Roman numerals
        p=re.compile("^\s*([IVXLC]+)/([0-9]+)\s*$")  # Leading whitespace + roman numeral characters + slash + nnn + whitespace
        m=p.match(s)
        if m is not None and len(m.groups()) == 2:
            self.Vol=roman.fromRoman(int(m.groups()[0]))
            self.Num=int(m.groups()[1])
            return self

        # Now look for a trailing decimal number
        p=re.compile("^.*?([0-9]+\.[0-9]+)\s*$")    # Leading characters + single non-digit + nnn + dot + nnn + whitespace
                                                    # the ? makes * a non-greedy quantifier
        m=p.match(s)
        if m is not None and len(m.groups()) == 1:
            self.Vol=None
            self.Num=float(m.groups()[0])
            return self

        # Now look for a single trailing number
        p=re.compile("^.*?([0-9]+)([a-zA-Z]?)\s*$")           # Leading stuff + nnn + optional single alphabetic character suffix + whitespace
        m=p.match(s)
        if m is not None and len(m.groups()) in [1, 2]:
            self.Vol=None
            self.Num=int(m.groups()[0])
            if len(m.groups()) == 2:
                self.Suffix=m.groups()[1]
            return self

        # Now look for trailing Roman numerals
        p=re.compile("^.*?\s+([IVXLC]+)\s*$")  # Leading stuff + mandatory whitespace + roman numeral characters + optional trailing whitespace
        m=p.match(s)
        if m is not None and len(m.groups()) == 1:
            self.Num=roman.fromRoman(m.groups()[0])
            return self

        # No good, return failure
        return self

    #=============================================================================
    def Suf(self):
        return self.Suffix if self.Suffix is not None else ""

    #=============================================================================
    # Format the Vol/Num/Whole information
    def FormatSerial(self):
        if self.Whole is not None and self.Vol is not None and self.Num is not None:
            return "#"+str(self.Whole)+"  (V"+str(self.Vol)+"#"+str(self.Num)+")"+self.Suf()

        if self.Whole is not None:
            return "#"+str(self.Whole)+self.Suf()

        if self.Vol is None and self.Num is None:
            return ""

        v="?"
        n="?"
        if self.Vol is not None:
            v=str(self.Vol)
        if self.Num is not None:
            n=str(self.Num)

        return "V"+v+"#"+n+self.Suf()


    # =====================================================================================
    # Function to attempt to decode an issue designation into a volume and number
    # Return a tuple of Volume and Number
    # If there's no volume specified, Volume is None and Number is the whole number
    # If we can't make sense of it, return (None, None), so if the 2nd member of the tuple is None, conversion failed.
    def DecodeIssueDesignation(self, str):
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
                i=0  # A dummy statement since all we want to do with an exception is move on to the next option.

        # This exhausts the single number possibilities
        # Maybe it's of the form Vnn, #nn (or Vnn.nn or Vnn,#nn)

        # Strip any leading 'v'
        if len(s) == 0:
            return (None, None)
        if s[0]=="v":
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

        # Now, the only legitimate character other than digits are the three delimiters, so translate them all to blanks and then split into the two digit strings
        spl=s.replace(".", " ").replace("#", " ").split()
        if len(spl) != 2:
            return (None, None)
        try:
            return (int(spl[0]), int(spl[1]))
        except:
            return (None, None)


    #==============================================================================
    # Given the contents of various table columns, attempt to extract serial information
    # This uses InterpretSerial for detailed decoding
    def ExtractSerial(self, volText, numText, wholeText, volNumText, titleText):
        wholeInt=None
        volInt=None
        numInt=None
        maybeWholeInt=None
        suffix=None

        if wholeText is not None:
            wholeInt=Helpers.InterpretNumber(wholeText)

        if volNumText is not None:
            ser=FanacSerial().InterpretSerial(volNumText)
            if ser.Vol is not None and ser.Num is not None:  # Otherwise, we don't actually have a volume+number
                volInt=ser.Vol
                numInt=ser.Num
                suffix=ser.Suffix

        if volText is not None:
            volInt=Helpers.InterpretNumber(volText)

        # If there's no vol, anything under "Num", etc., must actually be a whole number
        if volText is None:
            try:
                maybeWholeText=numText
                maybeWholeInt=int(maybeWholeText)
                numText=None
            except:
                pass

        # But if the *is* a volume specified, than any number not labelled "whole" must be a number within the volume
        if volText is not None and numText is not None:
            numInt=Helpers.InterpretNumber(numText)

        # OK, now figure out the vol, num and whole.
        # First, if a Vol is present, and an unambigious num is absent, the an ambigious Num must be the Vol's num
        if volInt is not None and numInt is None and maybeWholeInt is not None:
            numInt=maybeWholeInt
            maybeWholeInt=None

        # If the wholeInt is missing and maybeWholeInt hasn't been used up, make it the wholeInt
        if wholeInt is None and maybeWholeInt is not None:
            wholeInt=maybeWholeInt
            maybeWholeInt=None

        # Next, look at the title -- titles often have a serial designation at their end.

        if titleText is not None:
            # Possible formats:
            #   n   -- a whole number
            #   n.m -- a decimal number
            #   Vn  -- a volume number, but where's the issue?
            #   Vn[,] #m  -- a volume and number-within-volume
            #   Vn.m -- ditto
            ser=FanacSerial().InterpretSerial(titleText if type(titleText) is not tuple else titleText[0])

            # Some indexes have fanzine names ending in <month> <year>.  We'll detect these by looking for a trailing number between 1930 and 2050, and reject
            # getting vol/ser, etc., from the title if we find it.
            if ser.Num is None or ser.Num < 1930 or ser.Num > 2050:

                if ser.Vol is not None and ser.Num is not None:
                    if volInt is None:
                        volInt=ser.Vol
                    if numInt is None:
                        numInt=ser.Num
                    if volInt != ser.Vol or numInt != ser.Num:
                        Helpers.Log("***Inconsistent serial designations: '"+str(volInt)+"' != '"+str(ser.Vol)+"'  or  "+str(numInt)+"!="+str(ser.Num), True)
                elif ser.Num is not None:
                    if wholeInt is None:
                        wholeInt=ser.Num
                    if wholeInt != ser.Num:
                        Helpers.Log("***Inconsistent serial designations: '"+str(wholeInt)+"' != '"+str(ser.Num)+"'", True)

                if ser.Whole is not None:
                    wholeInt=ser.Whole

                suffix=ser.Suffix

        self.Vol=volInt
        self.Num=numInt
        self.Whole=wholeInt
        self.Suffix=suffix
        return self

