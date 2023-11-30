import re
import string
import argparse
import random

#Required for image processing
import imageio.v3 as iio
#Required for bytestring->bits conversion
from bitstring import BitArray
#Required for dictionary lookups
from english_words import get_english_words_set

#Default list of characters
# From Suen's paper, where they sourced from Thorndike et al.; Table IV, (d)
# Generated by alternating from Group A to Group B by the frequency in the table.
'''
C. Y. Suen, “n-gram statistics for natural language understanding and
text processing,” IEEE Transactions on Pattern Analysis and Machine
Intelligence, vol. PAMI-1, pp. 164–172, April 1979.
'''
'''
E. L. Thorndike and I. Lorge, The Teacher's Word Book of
30,000 Words. New York: Teachers College Press, 1944.
'''

DEFAULT_GROUPA = 'EAHISLUMCBKJQ'
DEFAULT_GROUPB = 'TONRDWFYGPVXZ'

#Convenience function that converts a bytestring to a list of bits
def bits_from_bytestring(bytestring):
    return BitArray(bytestring).bin

#Converts list of bits into a byte
def bytes_from_bits(bit_list):
    #Fail out if less than a full byte was provided
    if len(bit_list) < 8:
        return b''
    #Raise to power to convert, from low bit to high bit
    ret = bit_list[-1]
    ret += bit_list[-2] * 2**1
    ret += bit_list[-3] * 2**2
    ret += bit_list[-4] * 2**3
    ret += bit_list[-5] * 2**4
    ret += bit_list[-6] * 2**5
    ret += bit_list[-7] * 2**6
    ret += bit_list[-8] * 2**7
    return ret.to_bytes()
    
#Converts list of bits into a bytestring
def bytestring_from_bits(bit_list):
    ret = b''
    #Iterate through the bits in jumps of eight
    for b in range(0, len(bit_list), 8):
        #Convert the eight bits into a byte
        ret += bytes_from_bits(bit_list[b:b+8])
    return ret

#Function to get bit information from an image
# Grabs the LSB of the RGB values, starting from the beginning of the image
def get_stream_from_image(imagepath, bytes=100):
    out = []
    #Use imageio to read the image data from disk
    img = iio.imread(imagepath)
    #Calculate the number of required bits
    bits = bytes*8
    #Image data is stored in a multi-dimensional array:
    # img[col][row], where the RGB values are stored in that order
    for i in img:
        for p in i:
            #Get LSB from red value
            out.append(int(p[0] & 0b1))
            #Get LSB from green value
            out.append(int(p[1] & 0b1))
            #Get LSB from blue value
            out.append(int(p[2] & 0b1))
            #Break inner if enough bits have been collected
            if len(out) > bits: break
        #Break outer if enough bits have been collected
        if len(out) > bits: break
    
    #Truncate bits to correct length and convert to bytestring
    return bytestring_from_bits(out[:bits])
    
def get_stream_from_text(textstring):
    if isinstance(textstring, str):
        return textstring.encode('ascii')

#Convenience function. Does XOR of two bytestrings, one byte at a time
def xor_bytes(msgbytes, imgbytes):
    outbytes = b''
    #Iterate through the length of the msgbytes to encode
    for i in range(len(msgbytes)):
        #XOR the two specified bytes, and convert to bytes
        outbytes += (msgbytes[i] ^ imgbytes[i]).to_bytes()
        
    #Return the XOR
    return outbytes
    
#Convenience function. Does XOR of a key and a bytestring
def xor_key(key, otherbytes):
    #Expand the key until it's larger than the other bytestring
    while len(key) < len(otherbytes):
        key += key
    #Truncate the key to match the size of the other bytestring
    key = key[:len(otherbytes)]
    #Fix the key to be a bytestring, if necessary
    if isinstance(key, str):
        key = key.encode()
    #Return the XOR
    return xor_bytes(key, otherbytes)
    
#Encode a message
def encode(message, imagepath, key=None, verbose=False):
    #convert message to bytes
    msgbytes = get_stream_from_text(message)
    if verbose:
        print(msgbytes)
        print(bits_from_bytestring(msgbytes))
    
    #get number of bits from image
    imgbytes = get_stream_from_image(imagepath, bytes=len(msgbytes))
    if verbose:
        print(imgbytes)
        print(bits_from_bytestring(imgbytes))
    
    #get required parity as bytestring
    xxx = xor_bytes(msgbytes, imgbytes)
    if verbose:
        print(xxx)
    
    #add key, if needed
    if key:
        xxx = xor_key(key, xxx)
    
    #turn bytestring into parity bits
    parity = bits_from_bytestring(xxx)
    if verbose:
        print(parity)
    
    #return parity
    return parity
    
#Decodes a message
def decode(cover, imagepath, groupa, groupb, vowels=True, small=True, byword=False, key=None):
    #if requested, ignore smaller words during the decoding process
    if not small:
        #check middle for short word
        cover = re.sub('[^A-Z][A-Z]{1,3}[^A-Z]', '', cover, flags=re.I)
        #check for start of string short word
        cover = re.sub('^[A-Z]{1,3}[^A-Z]', '', cover, flags=re.I)
        #check for end of string short word
        cover = re.sub('[^A-Z][A-Z]{1,3}$', '', cover, flags=re.I)
        
    #if requested, ignore vowels
    if not vowels:
        cover = re.sub('[aeiouy]', '', cover, flags=re.I)
        
    #If doing by word instead of by letter
    if byword:
        #Get first character
        justfirsts = re.findall('^[A-Z]', cover, flags=re.I)
        #Get first character in each word
        justfirsts.extend(re.findall('[^A-Z][A-Z]', cover, flags=re.I))
        #Fix regex output and turn into string
        cover = ''.join([x[-1] for x in justfirsts])
        
    #convert the cover string into a bit string based upon parity groupings
    cover = cover_to_bits(cover, groupa, groupb)
    
    #convert the bit string into bytes so that they can be XOR
    coverbytes = bytestring_from_bits(cover)
    
    #get number of bits from image
    imgbytes = get_stream_from_image(imagepath, bytes=len(coverbytes))
    
    #remove key, if it's there
    if key:
        imgbytes = xor_key(key, imgbytes)
        
    #get original bytes
    output = xor_bytes(coverbytes, imgbytes)
    
    return output
    
#Convenience function. Converts provided cover text into bit string
def cover_to_bits(cover, groupa, groupb):
    #Remove any existing 0 or 1 characters to avoid poisoning the process by mistake
    cover = re.sub('[01]', '', cover)
    #Replace Group A with '0' across the string
    cover = re.sub('[{}]'.format(groupa), '0', cover, flags=re.I)
    #Replace Group B with '1' across the string
    cover = re.sub('[{}]'.format(groupb), '1', cover, flags=re.I)
    #Find all '0' and '1' characters that were replaced, thereby throwing away other characters
    cover = re.findall('0|1', cover)
    #Rejoin the list returned by re into a string
    cover = [int(x) for x in ''.join(cover)]
    
    return cover
    
#Convenience function. Builds regex to search in a word string
# Only needed for word recommendations
def make_parity_string(parity, zeroes, ones, vowels, byword):
    parityre = ''
    if not parity:
        return parityre
    #If vowels are being ignored, they must be removed from the character groups
    if not vowels:
        #Add an optional vowel at the start of the word
        parityre += '[AEIOUY]*'
        #Remove vowels from both groups
        zeroes = re.sub('[AEIOUY]', '', zeroes, flags=re.I)
        ones = re.sub('[AEIOUY]', '', ones, flags=re.I)
        
    if byword:
        if parity[0] == '0':
            parityre = '[{}]'.format(zeroes)
        elif parity[0] == '1':
            parityre = '[{}]'.format(ones)
        return parityre+'[A-Z]*'
        
    #Iterate through the parity listing
    for i in parity:
        #If it's a '0', replace with regex for zeroes group
        if i == '0':
            parityre += '[{}]'.format(zeroes)
        #If it's a '1', replace with regex for ones group
        elif i == '1':
            parityre += '[{}]'.format(ones)
        #If vowels are being ignored, add an optional vowel afterwards
        # to allow any number of vowels between consonants
        if not vowels:
            parityre += '[AEIOUY]*'
    
    return parityre
    
#Convenience function. Needs to return a space separated listing of words
# Only needed for word recommendations
def get_dictionary_string():
    web2lowerset = get_english_words_set(['web2'], lower=True)
    allwords = ' '.join(list(web2lowerset))
    
    return allwords
    
#Function to recommend words for parity matching
# parity: string list of parity bits (1010101010)
# cover: text generated so far that this function will skip (hello friend)
# zeroes: list of characters to replace with '0'
# ones: list of characters to replace with '1'
# outpath: location to write (via appending) the recommendations to
# vowels: should vowels be used (default True)
# small: should small words be used (default True)
# byword: use only the first letter of a word for parity check
# verbose: manually specified, prints information for debugging
# quiet: flag to suppress output, used by randomization function
def recommend_words(parity, cover, zeroes, ones, outpath, vowels=True, small=True, byword=False, verbose=False, quiet=False):
    #Get a space separated list of words
    allwords = get_dictionary_string()
    
    #If small words are being ignored, remove any short words from the dictionary
    if not small:
        #check middle for short word
        allwords = re.sub(' [A-Z]{1,3} ', '', allwords, flags=re.I)
        #check for start of string short word
        allwords = re.sub('^[A-Z]{1,3} ', '', allwords, flags=re.I)
        #check for end of string short word
        allwords = re.sub(' [A-Z]{1,3}$', '', allwords, flags=re.I)
        
    #If vowels are being ignored, remove all vowels from the cover text
    if not vowels:
        cover = re.sub('[aeiouy]', '', cover, flags=re.I)
        
    #Convert cover text to bit listing to determine how much of the parity list to skip
    c = cover_to_bits(cover, zeroes, ones)
    
    #List to hold findings
    pout_total = []
    
    #Iterate through the parity, starting with the end of the cover string
    for i in range(len(c), len(parity)):
        #pstring is the list of parity for which a word match is being searched
        pstring = parity[len(c):i+1]
        #Get the regex for the given parity based upon the letter listings and optional vowels
        parityre = make_parity_string(pstring, zeroes, ones, vowels, byword)
        #Find all of the matching words in the word list
        pout = re.findall(' {} '.format(parityre), allwords, flags=re.I)
        pout = [x.strip() for x in pout]
        pout.sort()
        if pout:
            #Only output to screen if not quiet
            if not quiet:
                print('Length: {}'.format(i-len(c)))
                print('Parity: {}'.format(pstring))
                print('Remaining: {}'.format(parity[i:]))
                if verbose:
                    print('Regex: " {} "'.format(parityre))
                print(pout)
            
            printstr = ''
            for p in pout:
                #Add all words to the findings, with context
                pout_total.append([pstring, p, parity[i:]])
                #And add to the output string, should it be needed
                if verbose:
                    printstr += '{} {} {}\n'.format(pstring, p, parity[i:])
                else:
                    printstr += '{} {}\n'.format(p, parity[i:])
            #Output to disk if requested
            if outpath:
                with open(outpath, 'a') as f:
                    f.write(printstr)
            if byword:
                break
                        
    return pout_total
                            
#Function to randomly choose words for parity matching
# parity: string list of parity bits (1010101010)
# cover: text generated so far that this function will skip (hello friend)
# zeroes: list of characters to replace with '0'
# ones: list of characters to replace with '1'
# outpath: location to write (via appending) the recommendations to
# vowels: should vowels be used (default True)
# small: should small words be used (default True)
# byword: use only the first letter of a word for parity check
def make_random_words(parity, cover, zeroes, ones, outpath, vowels=True, small=True, byword=False):
    remaining_parity = parity
    out_string = []
    #Iterate until the parity list has been exhausted
    while len(remaining_parity) > 0:
        #Get a list of recommendations
        pout_total = recommend_words(remaining_parity, '', zeroes, ones, outpath, vowels=vowels, small=small, byword=byword, quiet=True)
        #Quit if no recommendations were found or there are too few parity characters left (if not using small words)
        if (not pout_total) or ((not small) and len(remaining_parity) <= 3):
            print('Left-over parity: {}'.format(remaining_parity))
            break
        #Randomly choose a word
        rchoice = random.choice(pout_total)
        #Add the word itself to the output string
        out_string.append(rchoice[1])
        #Remove the utilized parity bits from the parity string
        if byword:
            remaining_parity = remaining_parity[1:]
        else:
            remaining_parity = remaining_parity[len(rchoice[0]):]
    
    print(' '.join(out_string))

def main():
    parser = argparse.ArgumentParser()   
    subparsers = parser.add_subparsers(dest='operation')

    #Message encoding subparser
    enc = subparsers.add_parser('encode', help='Encode a message')
    enc.add_argument('-i', '--image', action='store', help='Path the image used for cover', required=True)
    enc.add_argument('-m', '--message', action='store', help='Message to encode', required=True)
    enc.add_argument('-k', '--key', action='store', help='Optional XOR key')
    
    #Message decoding subparser
    dec = subparsers.add_parser('decode', help='Decode a message')
    dec.add_argument('-i', '--image', action='store', help='Path the image used for cover', required=True)
    dec.add_argument('-c', '--cover', action='store', help='Cover text', required=True)
    dec.add_argument('-k', '--key', action='store', help='Optional XOR key')
    dec.add_argument('-a', '--groupa', action='store', default=DEFAULT_GROUPA.upper(), 
                    help='List of characters to use for Group A parity (zero); default="{}"'.format(DEFAULT_GROUPA.upper()))
    dec.add_argument('-b', '--groupb', action='store', default=DEFAULT_GROUPB.upper(),
                    help='List of characters to use for Group B parity (one); default="{}"'.format(DEFAULT_GROUPB.upper()))
    dec.add_argument('-v', '--vowels', action='store_false', default=True,
                    help='If flagged, ignore vowels in processing cover text (AEIOUY)')
    dec.add_argument('-s', '--small', action='store_false', default=True,
                    help='If flagged, ignore small words (<= three in length)')
    dec.add_argument('-l', '--byword', action='store_true', default=False,
                    help='If flagged, do parity by first letter of the word, rather than by individual character')
    
    #Word suggestion subparser
    par = subparsers.add_parser('words', help='Help with creating cover text')
    par.add_argument('-p', '--parity', action='store', help='List of the parity bits', required=True)
    par.add_argument('-c', '--cover', action='store', help='Cover message created so far', default='')
    par.add_argument('-o', '--output', action='store', help='Output the parity suggestions to a file')
    par.add_argument('-r', '--random', action='store_true', help='Randomly pick words based upon the parity', default=False)
    par.add_argument('-a', '--groupa', action='store', default=DEFAULT_GROUPA.upper(), 
                    help='List of characters to use for Group A parity (zero); default="{}"'.format(DEFAULT_GROUPA.upper()))
    par.add_argument('-b', '--groupb', action='store', default=DEFAULT_GROUPB.upper(),
                    help='List of characters to use for Group B parity (one); default="{}"'.format(DEFAULT_GROUPB.upper()))
    par.add_argument('-v', '--vowels', action='store_false', default=True,
                    help='If flagged, ignore vowels in processing cover text (AEIOUY)')
    par.add_argument('-s', '--small', action='store_false', default=True,
                    help='If flagged, ignore small words (<= three in length)')
    par.add_argument('-l', '--byword', action='store_true', default=False,
                    help='If flagged, do parity by first letter of the word, rather than by individual character')
    
    args = parser.parse_args()

    if not args.operation == 'encode':
        #Check to ensure that the letter groups have the expected 26 characters
        diff = set(string.ascii_uppercase) - set(args.groupa.upper() + args.groupb.upper())
        #Unless vowels are not being using. In that case, throw them out
        if not args.vowels:
            diff = diff - set('AEIOUY')
        if diff:
            print('GroupA and GroupB must cover the entire ASCII alphabet (A-Z)')
            return
        
    #Conduct encoding
    if args.operation == 'encode':
        parity = encode(args.message, args.image, args.key)
        print('Required cover text parity: {}'.format(parity))
    #Conduct decoding
    elif args.operation == 'decode':
        msg = decode(args.cover, args.image, args.groupa, args.groupb, args.vowels, args.small, args.byword, args.key)
        print('Recovered message: {}'.format(msg))
    #Try to suggest words
    elif args.operation == 'words':
        #Randomly grab a whole strings worth
        if args.random:
            make_random_words(args.parity, args.cover, args.groupa, args.groupb, args.output, args.vowels, args.small, args.byword)
        #Show all possibilities for the user to pick
        else:
            recommend_words(args.parity, args.cover, args.groupa, args.groupb, args.output, args.vowels, args.small, args.byword)
    
if __name__ == '__main__':
    main()