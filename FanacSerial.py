from dataclasses import dataclass, field
import roman
import re

@dataclass()
class FanacSerial:
    Vol: int = None
    Num: int = None
    Whole: int = None

    #=============================================================================================
    # If there's a trailing Vol+Num designation at the end of a string, interpret it.
    # We return a tuple of a (Vol, Num) or a (None, Num)
    # We accept:
    #       ...Vnn[,][ ]#nnn[ ]
    #       ...nn[ ]
    #       ...nnn/nnn[  ]
    #       ...nn.mm
    def InterpretSerial(self, s):

        s=s.upper()

        # First look for a Vol+Num designation
        p=re.compile("(.*)V([0-9]+),?\s*#([0-9]+)\s*$")
        m=p.match(s)
        if m is not None and len(m.groups()) == 2:
            self.Vol=int(m.groups()[0])
            self.Num=int(m.groups()[1])
            return self

        # Now look for nnn/nnn
        p=re.compile("^.*([0-9]+)/([0-9]+)\s*$")
        m=p.match(s)
        if m is not None and len(m.groups()) == 2:
            self.Vol=int(m.groups()[0])
            self.Num=int(m.groups()[1])
            return self

        # Now look for xxx/nnn, where xxx is in Roman numerals
        p=re.compile("^\s*([IVXLC]+)/([0-9]+)\s*$")
        m=p.match(s)
        if m is not None and len(m.groups()) == 2:
            self.Vol=roman.fromRoman(int(m.groups()[0]))
            self.Num=int(m.groups()[1])
            return self

        # Now look for a trailing decimal number
        p=re.compile("^.*\D([0-9]+\.[0-9]+)\s*$")       # the \D demands a non-digit character; it's to stop the greedy parser.
        m=p.match(s)
        if m is not None and len(m.groups()) == 1:
            self.Vol=None
            self.Num=float(m.groups()[0])
            return self

        # Now look for a single trailing number
        p=re.compile("^.*\D([0-9]+)\s*$")
        m=p.match(s)
        if m is not None and len(m.groups()) == 1:
            self.Vol=None
            self.Num=int(m.groups()[0])
            return self

        # No good, return failure
        return self



    #=============================================================================
    # Format the Vol/Num/Whole information
    def FormatSerial(self):
        if self.Whole is not None and self.Whole != 0 and self.Vol is not None and self.Vol !=0 and self.Num is not None and self.Num != 0:
            return "#"+str(self.Whole)+"  (V"+str(self.Vol)+"#"+str(self.Num)+")"

        if self.Whole is not None and self.Whole != 0:
            return "#"+str(self.Whole)

        if self.Vol is None and self.Num is None:
            return ""

        v="?"
        n="?"
        if self.Vol is not None and self.Vol!=0:
            v=str(self.Vol)
        if self.Num is not None and self.Num!=0:
            n=str(self.Num)

        return "V"+v+"#"+n


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
        if len(s)==0:
            return (None, None)
        if s[0]=="#":
            s=s[1:]
            if len(s)==0:
                return (None, None)
            try:
                return (None, int(s))
            except:
                i=0  # A dummy statement since all we want to do with an exception is move on to the next option.

        # This exhausts the single number possibilities
        # Maybe it's of the form Vnn, #nn (or Vnn.nn or Vnn,#nn)

        # Strip any leading 'v'
        if len(s)==0:
            return (None, None)
        if s[0]=="v":
            s=s[1:]
            if len(s)==0:
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
        if len(spl)!=2:
            return (None, None)
        try:
            return (int(spl[0]), int(spl[1]))
        except:
            return (None, None)