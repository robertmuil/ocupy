#!/usr/bin/env python
"""A helper module that collects some useful auxillary functions."""

from numpy import asarray, ma
import numpy as np
import cPickle
import os

have_image_library=True
try:
    from scipy.misc import toimage, fromimage #@UnresolvedImport
except ImportError:
    have_image_library=False

def isiterable(some_object):
    """
    determine if an object can be iterated or not.
    """
    try:
        iter(some_object)
    except TypeError:
        return False
    return True

def all_same(items):
    """
       http://stackoverflow.com/q/3844948/
       TODO: is this the most efficient for NumPy arrays?
       TODO: handle empty sequences.

       >>> all_same([1,1,1])
       True

       >>> all_same([1,2,1])
       False

       >>> all_same(None)
       True

       >>> all_same([1])
       True

       >> all_same([])
       True

       """
    return items is None or list(items).count(items[0]) == len(items)

def ma_nans(shape):
    """
    Use instead of ma.masked_all().
    Returns a completely masked array whose underlying data is all NaNs.

    ma.masked_all creates an uninitialized array (with np.empty) which can
    cause warnings and worse in later code if arithmetic is attempted on the
    array, even if it is masked.
    """
    aa = np.ma.ones(shape) * np.nan
    aa.set_fill_value(np.nan)
    aa.mask = True
    return aa

if have_image_library:
    def imresize(arr, newsize, interp='bicubic', mode=None):
        """
        resize a matrix to the desired dimensions. May not always lead to best
        behavior at borders. If possible, fixation density maps and features
        should directly be computed in the desired size.

        Parameters
        ----------
        arr : array_like
            Input data, in any form that can be converted to an array with at
            least 2 dimensions
        newsize : 2 element tupel
            newsize[0] is the new height, newsize[1] the new width of the image
        interp : string
            specifies the interpolation method. Possible values are nearest, 
            bilinear, and bicubic. Defaults to bicubic.
        mode : string
            specifies the mode with which arr is transformed to an image. Per
            default, if arr is a valid (N,3) byte-array giving the RGB values
            (from 0 to 255) then mode='P'. For 2D arrays, the data type of the
            values is used.

        Returns
        -------
        out : ndarray
            The resized version of the input array
        """
        newsize = list(newsize)
        newsize.reverse()
        newsize = tuple(newsize)
        arr = asarray(arr)
        func = {'nearest':0, 'bilinear':2, 'bicubic':3, 'cubic':3}
        if not mode and arr.ndim == 2:
            mode = arr.dtype.kind.upper()
        img = toimage(arr, mode=mode)

        img = img.resize(newsize, resample = func[interp])
        return fromimage(img)

    
def randsample(vec, nr_samples, with_replacement = False):
    """
    Draws nr_samples random samples from vec.
    """
    if not with_replacement:
        return np.random.permutation(vec)[0:nr_samples]
    else:
        return np.asarray(vec)[np.random.randint(0, len(vec), nr_samples)]

def ismember(ar1, ar2): 
    """ 
    A setmember1d, which works for arrays with duplicate values 
    """
    return np.in1d(ar1, ar2)

def calc_resize_factor(prediction, image_size):
    """
    Calculates how much prediction.shape and image_size differ.
    """
    resize_factor_x = prediction.shape[1] / float(image_size[1])
    resize_factor_y = prediction.shape[0] / float(image_size[0])
    if abs(resize_factor_x - resize_factor_y) > 1.0/image_size[1] :
        raise RuntimeError("""The aspect ratio of the fixations does not
                              match with the prediction: %f vs. %f"""
                              %(resize_factor_y, resize_factor_x))
    return (resize_factor_y, resize_factor_x)
    
def dict_2_mat(data, fill = True):
    """
    Creates a NumPy array from a dictionary with only integers as keys and
    NumPy arrays as values. Dimension 0 of the resulting array is formed from
    data.keys(). Missing values in keys can be filled up with np.nan (default)
    or ignored.

    Parameters
    ----------
    data : dict
        a dictionary with integers as keys and array-likes of the same shape
        as values
    fill : boolean
        flag specifying if the resulting matrix will keep a correspondence
        between dictionary keys and matrix indices by filling up missing keys
        with matrices of NaNs. Defaults to True

    Returns
    -------
    numpy array with one more dimension than the values of the input dict
    """
    if any([type(k) != int for k in data.keys()]):
        raise RuntimeError("Dictionary cannot be converted to matrix, " +
                            "not all keys are ints")
    base_shape = np.array(data.values()[0]).shape
    result_shape = list(base_shape)
    if fill:
        result_shape.insert(0, max(data.keys()) + 1)
    else:
        result_shape.insert(0, len(data.keys()))
    result = np.empty(result_shape) + np.nan
        
    for (i, (k, v)) in enumerate(data.items()):
        v = np.array(v)
        if v.shape != base_shape:
            raise RuntimeError("Dictionary cannot be converted to matrix, " +
                                        "not all values have same dimensions")
        result[fill and [k][0] or [i][0]] = v
    return result
        
def dict_fun(data, function):
    """
    Apply a function to all values in a dictionary, return a dictionary with
    results.

    Parameters
    ----------
    data : dict
        a dictionary whose values are adequate input to the second argument
        of this function. 
    function : function
        a function that takes one argument

    Returns
    -------
    a dictionary with the same keys as data, such that
    result[key] = function(data[key])
    """
    return dict((k, function(v)) for k, v in data.items())

def snip_string_middle(string, max_len=20, snip_string='...'):
    """
    >>> snip_string_middle('this is long', 8)
    'th...ong'
    >>> snip_string_middle('this is long', 12)
    'this is long'
    >>> snip_string_middle('this is long', 8, '~')
    'thi~long'
    

    """
    #warn('use snip_string() instead', DeprecationWarning)
    if len(string) <= max_len:
        new_string = string
    else:
        visible_len = (max_len - len(snip_string))
        start_len = visible_len//2
        end_len = visible_len-start_len
        
        new_string = string[0:start_len]+ snip_string + string[-end_len:]
    
    return new_string
   
def snip_string(string, max_len=20, snip_string='...', snip_point=0.5):
    """
    Snips a string so that it is no longer than max_len, replacing deleted
    characters with the snip_string.
    The snip is done at snip_point, which is a fraction between 0 and 1,
    indicating relatively where along the string to snip. snip_point of
    0.5 is the middle.
    >>> snip_string('this is long', 8)
    'th...ong'
    >>> snip_string('this is long', 8, snip_point=1)
    'this ...'
    >>> snip_string('this is long', 12)
    'this is long'
    >>> snip_string('this is long', 8, '~')
    'thi~long'
    >>> snip_string('this is long', 8, '~', 1)
    'this is~'
    
    """
    if len(string) <= max_len:
        new_string = string
    else:
        visible_len = (max_len - len(snip_string))
        start_len = int(visible_len*snip_point)
        end_len = visible_len-start_len
        
        new_string = string[0:start_len]+ snip_string
        if end_len > 0:
            new_string += string[-end_len:]
    
    return new_string 

def find_common_beginning(string_list, boundary_char = None):
    """Given a list of strings, finds finds the longest string that is common
    to the *beginning* of all strings in the list.
    
    boundary_char defines a boundary that must be preserved, so that the
    common string removed must end with this char.
    """
    
    common=''
    
    # by definition there is nothing common to 1 item...
    if len(string_list) > 1:
        shortestLen = min([len(el) for el in string_list])
        
        for idx in range(shortestLen):
            chars = [s[idx] for s in string_list]
            if chars.count(chars[0]) != len(chars): # test if any chars differ
                break
            common+=chars[0]
    
        
    if boundary_char is not None:
        try:
            end_idx = common.rindex(boundary_char)
            common = common[0:end_idx+1]
        except ValueError:
            common = ''
    
    return common

def factorise_strings (string_list, boundary_char=None):
    """Given a list of strings, finds the longest string that is common
    to the *beginning* of all strings in the list and
    returns a new list whose elements lack this common beginning.
    
    boundary_char defines a boundary that must be preserved, so that the
    common string removed must end with this char.
    
    >>> cmn='something/to/begin with?'
    >>> blah=[cmn+'yes',cmn+'no',cmn+'?maybe']
    >>> (blee, bleecmn) = factorise_strings(blah)
    >>> blee
    ['yes', 'no', '?maybe']
    >>> bleecmn == cmn
    True
    
    >>> blah = ['de.uos.nbp.senhance', 'de.uos.nbp.heartFelt']
    >>> (blee, bleecmn) = factorise_strings(blah, '.')
    >>> blee
    ['senhance', 'heartFelt']
    >>> bleecmn
    'de.uos.nbp.'
    
    >>> blah = ['/some/deep/dir/subdir', '/some/deep/other/dir', '/some/deep/other/dir2']
    >>> (blee, bleecmn) = factorise_strings(blah, '/')
    >>> blee
    ['dir/subdir', 'other/dir', 'other/dir2']
    >>> bleecmn
    '/some/deep/'
    
    >>> blah = ['/net/store/nbp/heartFelt/data/ecg/emotive_interoception/p20/2012-01-27T09.01.14-ecg.csv', '/net/store/nbp/heartFelt/data/ecg/emotive_interoception/p21/2012-01-27T11.03.08-ecg.csv', '/net/store/nbp/heartFelt/data/ecg/emotive_interoception/p23/2012-01-31T12.02.55-ecg.csv']
    >>> (blee, bleecmn) = factorise_strings(blah, '/')
    >>> bleecmn
    '/net/store/nbp/heartFelt/data/ecg/emotive_interoception/'
    
    rmuil 2012/02/01
    """
    
    cmn = find_common_beginning(string_list, boundary_char)
    
    new_list = [el[len(cmn):] for el in string_list]

    return (new_list, cmn)

class Memoize:
    """
    Memoize with mutable arguments
    """
    def __init__(self, function):
        self.function = function
        self.memory = {}

    def __call__(self, *args, **kwargs):
        hash_str = cPickle.dumps(args) + cPickle.dumps(kwargs)
        if not hash_str in self.memory:
            self.memory[hash_str] = self.function(*args, **kwargs)
        return self.memory[hash_str]

#def pad_vector0(data,center, window = [-7, 7]):
#	"""
#	Takes a specific part a vector, namely the window around the center index.
#	This works even if the window exceeds the extent of the input vector,
#	by padding with the pad_element.
#	
#	NB: the interpretation of the window argument needs some explanation:
#	the elements are interpreted as *inclusive* offsets from the center.
#	When the second argument is less than the first, the result is odd...
#	Niklas?
#	 
#	Returns a copy of the index.
#	Author: nwilming@UoS.de
#	"""
#	wlen = abs(window[0]-window[1]-1)
#	new_center = abs(window[0]-window[1]-1)/2
#	num_pre = new_center - center
#	d_start = 0
#	if num_pre < 0:
#		d_start = abs(num_pre)
#		num_pre = 0
#	out = [np.NaN]*num_pre + list(data[d_start:])
#	if len(out) > wlen:
#		return np.array(out[0:wlen])
#	else:
#		return np.array(out + [np.NaN]*(wlen-len(out)))

def pad_vector(data, center, window, pad_element=np.NaN):
    """
    Takes a specific part a vector, namely the window around the center index.
    This works even if the window exceeds the extent of the input vector,
    by padding with the pad_element.
    
    NB: This is an important function. It is used for much analysis.
    
    'center' is the index into data around which to build the window.
    
    The window is interpreted also as indices and are relative to the center,
    so that the
    new vector will go from (center+window[0]) to (center+window[1]).
    NB: This is a little non-intuitive because of the non-inclusive indexing in
    Python, which will mean that the element at center+window[1] will *not*
    be included in the output. This makes sense if the window is seen as indices:
	    >>> [0,1,2,3][0:3]
	    [0, 1, 2]
    
    The size of the output will be window[1]-window[0]
    
    Returns a copy of the input.
    Output will be a masked array if input is masked array, an ndarray if
     the input is an ndarray, otherwise a list.
    
    Author: rmuil@UoS.de
    
    Examples:
    
    Be aware that the window elements are indices, not lengths:
	    >>> pad_vector(range(10), center=5, window=[-2, 3])
	    [3.0, 4.0, 5.0, 6.0, 7.0]
	    >>> len(_)
	    5
    
    The pad_element determines the output data type:
	    >>> pad_vector(range(10), center=5, window=[-2, 3],pad_element=-1)
	    [3, 4, 5, 6, 7]
    
    Exceeding input size will cause padding:
	    >>> pad_vector(range(10), center=5, window=[-7, 7])
	    [nan, nan, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, nan, nan]
	    >>> len(_)
	    14
    
    Output element type is determined by pad_element type:
	    >>> pad_vector(range(10), center=5, window=[-7, 7], pad_element=-1)
	    [-1, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1, -1]
    
    If input is an array, output will also be:
	    >>> pad_vector(np.arange(10), center=5, window=[-1, 2])
	    array([ 4.,  5.,  6.])
    
    If input is a masked array, output will also be:
	    >>> pad_vector(ma.arange(10), center=5, window=[-1, 7]) # doctest:+ELLIPSIS
	    masked_array(data = [4.0 5.0 6.0 7.0 8.0 9.0 -- --],
	                 mask = [False False False False False False  True  True],
	           fill_value = nan)
	    ...
	    >>> _.filled()
	    array([  4.,   5.,   6.,   7.,   8.,   9.,  nan,  nan])

    The start index can also be after the end of the input:
	    >>> pad_vector(range(10), center=5, window=[5, 7])
	    [nan, nan]
    
    Likewise, the end index can be before the start of the input:
	    >>> pad_vector(range(10), center=5, window=[-15, -10])
	    [nan, nan, nan, nan, nan]

    Ending before start gives empty vector:
	    >>> pad_vector(range(10), center=5, window=[5, 0])
	    []

    
    """
    sidx = center + window[0]
    eidx = center + window[1]
    num_pre = 0
    num_post = 0
    
    dtype=type(pad_element)
    
    out_size = max(0,window[1]-window[0])
    out = ma.ones(out_size,dtype) * pad_element
    out.set_fill_value(pad_element)
    out.mask=True
    #print num_pre,sidx,eidx,num_post
    if sidx < 0:
        num_pre = -sidx
        sidx = 0
        if eidx < sidx:
            num_pre -= (sidx-eidx)
    if eidx < 0:
        eidx = 0
    elif eidx > len(data):
        num_post = eidx - len(data)
        eidx = len(data)
        if sidx > eidx:
            num_post -= (sidx-eidx)
    #print num_pre,sidx,eidx,num_post
    out[num_pre:out_size-num_post] = data[sidx:eidx]
    #out = [pad_element]*num_pre + list(data[sidx:eidx]) + [pad_element]*num_post

    if not isinstance(data, np.ndarray):
        out = list(out.filled())
    elif not isinstance(data, ma.MaskedArray):
        out = out.filled()

    return out

def align_vector(src, onset_src, onset_dst, len_dst,
                 pad_element=np.nan):
    """
    This is essentially a wrapper around pad_vector() tailored to the use-case
    for assimilating data from one hierarchical DataMat into another: that is,
    when two DataMats both contain time-indexed fields (multiple elements) and
    so for each element, the source element array must be aligned to the
    destination element array.
    
    >>> aa = align_vector([1, 2, 3, 4], 0, 2, 8)
    >>> print aa
    [nan, nan, 1.0, 2.0, 3.0, 4.0, nan, nan]
    
    >>> aa = align_vector(ma.array([1, 2, 3, 4]), 0, 2, 8)
    >>> print aa
    [-- -- 1.0 2.0 3.0 4.0 -- --]
    
    >>> align_vector([8, 7, 6, 5, 4, 3, 2, 1, 0, -1, -2, -3], 4, 2, 8, -99)
    [6, 5, 4, 3, 2, 1, 0, -1]
    
    """
    return pad_vector(src, onset_src, [-onset_dst, len_dst - onset_dst],
                      pad_element)

def expand_boolean_subindex(overall_idx, subidx):
    """
    subidx is a boolean index referencing a subset of an array that is the length
    of overall_idx, and overall_idx indicates where, in the original array, the
    subidx refers to.
    
    This function turns the subidx back into a boolean array that will reference
    the original array directly.
    
    Was constructed to allow indexing a DataMat using an index of a *subset* of
    that DataMat (as returned, for example, by the by_field() function).
    
    
    >>> ovi = np.array([0,1,1,1,0]).astype('bool')
    >>> si  = np.array([1,0,1]).astype('bool')
    >>> ei = expand_boolean_subindex(ovi,si)
    >>> ','.join(['%d'%d for d in ei])
    '0,1,0,1,0'
    
    >>> si  = np.array([0,0,1]).astype('bool')
    >>> ei = expand_boolean_subindex(ovi,si)
    >>> ','.join(['%d'%d for d in ei])
    '0,0,0,1,0'
    
    """
    
    positions = np.where(overall_idx)[0]
    false_positions = positions[~subidx]
    
    ei = overall_idx.copy()
    ei[false_positions] = False
    
    return ei

def factorise_field(dm, field_name, boundary_char=None, parameter_name=None):
    """This removes a common beginning from the data of the fields, placing
    the common element in a parameter and the different endings in the fields.
    
    if parameter_name is None, then it will be <field_name>_common.
    
    So far, it's probably only useful for the file_name.
    
    NB: this modifies the DataMat!
    
    TODO: remove field entirely if no unique elements exist.
    """

    old_data = dm.field(field_name)

    if isinstance(old_data[0], str) or isinstance(old_data[0], unicode):
        (new_data, common) = factorise_strings(old_data, boundary_char)
        new_data = np.array(new_data)
    else:
        raise NotImplementedError('factorising of fields not implemented for anything but string/unicode objects')

    if len(common) > 0:
        dm.__dict__[field_name] = new_data
        if parameter_name is None:
            parameter_name = field_name + '_common'
        dm.add_parameter(parameter_name, common)

def get_file_name(dm,
                  fname_field='file_name',
                  fpath_param='file_path'):
    """
    Convenience function to get the filename of a particular DataMat,
    which is potentially stored in a combination of parameter and field,
    as done with factorise_field.
    
    Will return the file_name of the first element in the DataMat.
    
    The names of the variables are not very strict, which is silly:
    this function will return the entire path of the file from which the
    first element of the DataMat came. This is composed of the 'file_path'
    and the 'file_name' which should actually be called something like 
    'file_dir' and 'file_fname' respectively. Oh well.
    
    """
    fname = None
    if fname_field in dm.fieldnames():
        if fpath_param in dm.parameters():
            fname = os.path.join(dm.parameter(fpath_param), dm.field(fname_field)[0])
        else:
            fname = dm.field(fname_field)[0]
    else:
        #ok, no field, must be only param
        if fname_field in dm.parameters():
            fname = dm.parameter(fname_field)
    
    return fname

if __name__ == '__main__':
    import doctest
    doctest.testmod()
