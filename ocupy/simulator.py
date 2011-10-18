#!/usr/bin/env python
"""This module implements a generator of data with given second-order dependencies"""

from math import asin, atan2, degrees, radians, ceil, cos, sin 
import random

from ocupy import fixmat
import spline_base
from progressbar import ProgressBar, Percentage, Bar
import numpy as np


class AbstractSim(object):
	def __init__(self):
		raise NotImplementedError
	def sample(self):
		raise NotImplementedError
	def parameters(self):
		raise NotImplementedError
	def finish(self):
		raise NotImplementedError


class FixGen(AbstractSim):
	'''
	Generates fixation data.
	The FixGen object creates a representation of the second order dependence structures
	between saccades contained in the fixmat given as input. It is then able to generate 
	and return a fixmat which replicates these dependencies, while consisting of different 
	fixations.
	In order to work, the initialized FixGen obejct has to initialize its data by calling
	the method initializeData():

			>>> gen = simulator.FixSim(fm)
			>>> gen.initializeData()
	
	Separating this time-consuming step from the initialization	is helpful in cases of 
	parallelization.
	Data is generated upon calling the method sample_many(num_samples = 1000).	
	'''
	
	def __init__(self, fm_name = '/home/student/s/sharst/Dropbox/NBP/fixmat_photos.mat'):
		'''
		Creates a new FixGen object upon a certain fixmat
		
		Parameters: 
			fm_name: string or ocupy.fixmat
				The fixation data to replicate in fixmat format.
				Note: If the first fixation in the set was always kept centered, 
				they have to be deleted prior to passing the fixmat to this function.				
		'''
		
		if type(fm_name)==str:
			self.fm = fixmat.FixmatFactory(fm_name)
		elif type(fm_name)==ocupy.FixMat.fixmat:
			self.fm = fm_name
		else:
			raise ValueError("Not a valid argument, insert fixmat or path to fixmat")
		
		if (min(self.fm.fix)==1):
			self.firstfixcentered = False
		else:
			self.firstfixcentered = True
			
		
	def initializeData(self):
		'''
		Prepares the data to be replicated. Calculates the second-order length and angle
		dependencies between saccades and stores them in a fitted histogram.
		'''
		ad, ld = anglendiff(self.fm, roll=1) 
		screen_diag = int(ceil((np.sum(np.array(self.fm.image_size)**2)**.5)
												/self.fm.pixels_per_degree))
		
		self.full_H1 = spline(ad[0],ld[0]/self.fm.pixels_per_degree,
							collapse=False,xdim=[-screen_diag,screen_diag])
		
		self.firstLengthsAngles_cumsum, self.firstLengthsAngles_shape = (
									compute_cumsum(self.fm, 'la'))
		self.probability_cumsum = np.cumsum(np.concatenate(self.full_H1))
		self.firstcoordinates_cumsum = compute_cumsum(self.fm,'coo')
		self.trajectoryLengths_cumsum, self.trajectoryLengths_borders = compute_cumsum(self.fm, 'len')
		
		# Counters for saccades that have to be canceled during the process
		self.canceled = 0
		self.minusSaccades = 0
		
		
	def _calc_xy(self, (x,y), angle, length):
		'''
		Calculates the coordinates after a specific saccade was made.
		
		Parameters:
			(x,y) : tuple of floats or ints
				The coordinates before the saccade was made
			angle : float or int
				The angle that the next saccade encloses with the display border
			length: float or int
				The length of the next saccade
		'''
		return (x+(cos(radians(angle))*length),
				y+(sin(radians(angle))*length))
			   
	def _draw(self, prev_angle = None, prev_length = None):
		'''
		Draws a new length- and angle-difference pair and calculates
		length and angle absolutes matching the last saccade drawn.
		
		Parameters:
			prev_angle : float, optional
				The last angle that was drawn in the current trajectory
			prev_length : float, optional
				The last length that was drawn in the current trajectory
			
			Note: Either both prev_angle and prev_length have to be given or none;
			if only one parameter is given, it will be neglected.
		'''
		if (prev_angle == None) or (prev_length == None):
			(length, angle) = np.unravel_index(drawFrom(self.firstLengthsAngles_cumsum),
					self.firstLengthsAngles_shape)
			angle = angle-((self.firstLengthsAngles_shape[1]-1)/2.0)
		else:
			J, I = np.unravel_index(drawFrom(self.probability_cumsum), self.full_H1.shape)
			angle = reshift((I-self.full_H1.shape[1]/2.0) + prev_angle)
			length = prev_length + ((J-self.full_H1.shape[0]/2.0)*self.fm.pixels_per_degree)
		return angle, length
	
	def parameters(self):
		return {'fixmat':self.fm, 'sampling_dist':self.full_H1}

	def finish(self):
		pass
	
	def sample_many(self, num_samples = 500):
		'''
		Generates a given number of trajectories, using the method sample(). 
		Returns a fixmat with the generated data.
		
		Parameters:
			num_samples : int, optional
				The number of trajectories that shall be generated. If not given,
				it is set to 500.
		'''		
		x = []
		y = []
		fix = []
		sample = []
		
		print "Simulating "+repr(num_samples)+" trajectories..."
		pbar = ProgressBar(widgets=[Percentage(),Bar()], maxval=num_samples).start()
		
		for s in xrange(0, num_samples):
			for i, (xs,ys) in enumerate(self.sample()):
				x.append(xs)
				y.append(ys)
				fix.append(i+1)
				sample.append(s)   
			
			pbar.update(s+1)
		fields = {'fix':np.array(fix),'y':np.array(y), 'x':np.array(x)}
		param = {'image_size':self.fm.image_size,'pixels_per_degree':self.fm.pixels_per_degree}
		out =  fixmat.VectorFixmatFactory(fields, param)
		pbar.finish()
		return out
	
	def sample(self):
		'''
		Draws a trajectory length, first coordinates, lengths, angles and 
		length-angle-difference pairs according to the empirical distribution. 
		Each call creates one complete trajectory.
		'''
		lenghts = []
		angles = []
		coordinates = []
		fix = []
		sample_size = int(round(drawFrom(self.trajectoryLengths_cumsum, borders=self.trajectoryLengths_borders)))
		
		if (self.firstfixcentered == True):
			coordinates.append([self.fm.image_size[1]/2,self.fm.image_size[0]/2])
		else:
			K,L=(np.unravel_index(drawFrom(self.firstcoordinates_cumsum),[self.fm.image_size[0],self.fm.image_size[1]]))
			coordinates.append([L,K])
			
		fix.append(1)
		while len(coordinates) < sample_size:
			if len(lenghts) == 0 and len(angles) == 0:			
				angle, length = self._draw(self)													   
			else:
				angle, length = self._draw(prev_angle = angles[-1], prev_length = lenghts[-1])  
						
			x, y = self._calc_xy(coordinates[-1], angle, length) 
			
			if (length<0):
				self.minusSaccades+=1
				pass # Drawn saccade length not possible
			else:
				coordinates.append([x,y])
				lenghts.append(length) 
				angles.append(angle)
				fix.append(fix[-1]+1)
		return coordinates
		
def anglendiff(fm, roll = 1, return_abs=False):
	'''
	Calculates the lengths and angles of the saccades contained in the fixmat
	as well as length- and angle differences between consecutive saccades.
	Returns a nested vector structure that gives these multi-order differences
	in the following order:
		
		>>> anglendiff(fm, roll = 2)
		Out: [[AngleDiffs 2nd order], [AngleDiffs 3rd order]], 
			 [[LengthDiffs 2nd order], [LengthDiffs 3rd order]]
		
	
	Parameters:	
		fm : ocupy.fixmat object 
			The fixmat with the data that shall be analyzed.
		roll : int, optional
			The maximum order of the dependence structure that shall be analyzed -1.
			
				>>> anglendiff(fm, roll=2)   # Analyzes the data up to third order
			
			If none is given, only the second order properties are calculated.
		return_abs : boolean, optional
			By default, the method returns only length-angle difference pairs. 
			If return_abs is set to true, the length and angle absolutes are returned
			as well.
			
				>>> angles, lengths, angle_diffs, length_diffs = 
							anglendiff(fm, return_abs = True)
	'''
	
	angle_diffs = []
	length_diffs = []
	lengths = []
	angles  = []
	
	for r in range(1, roll+1):
		heights = (fm.y - np.roll(fm.y,r)).astype(float)
		widths = (fm.x - np.roll(fm.x,r)).astype(float)
		
		heights[fm.fix<=min(fm.fix)+r-1]=float('nan')
		widths[fm.fix<=min(fm.fix)+r-1]=float('nan')
		
		lengths.append((widths**2+heights**2)**.5)
		angles.append(np.degrees(np.arctan2(heights,widths)))
		
		length_diffs.append(lengths[0] - np.roll(lengths[r-1],1))
		
		# -360: straight saccades, -180: return saccades, 0: straight saccades,
		# 180: return saccades, 360: no return saccades
		angle_diffs.append(angles[0] - np.roll(angles[r-1],1))
				
	if return_abs==True:
		return angles, lengths, angle_diffs, length_diffs
		
	else:
		return angle_diffs, length_diffs
			
def createHist(ld, ad, bins=[np.linspace(-36.5,36.5,74), np.linspace(-0.5,180.5,182)]):
	'''
	Creates and returns a 2D-histogram, typically of length and angle difference pairs.
	
	Parameters:
		ld : array 
				Values to be histogrammed along the x-axis, 
				typically length differences
		ad : array 
				Values to be histogrammed along the y-axis,
				typically angle differences
		bins : list of two arrays, optional
				The bin borders to be used for the histogram. 
				Defaults to [-36,36] on the y-axis and [0,180] on the x-axis, where
				36 is the screen diagonal of a typical screen.
	'''
	H, xedges, yedges = np.histogram2d(ld[~np.isnan(ld)], ad[~np.isnan(ad)], bins=bins)
	H = H / sum(sum(H))
	H[:,0]*=2  
	H[:,-1]*=2
	return H
	
def compute_cumsum(fm, arg):
	'''
	Creates a probability distribution, transforms it to a single row array
	and calculates its cumulative sum.
	
	Parameters:
		fm : ocupy.fixmat
			The fixmat to take the data from.
		arg : string
			arg can take one of the following values:
			'la' : The probability distribution is calculated over the lengths and angles
					of the very first saccades made on each image by the subjects.
			'coo' : The prob.dist. is calculated over the first coordinates 
					fixated on each image.
			'len' : The prob.dist. is calculated over the amount of saccades per 
					trajectory.
	Returns: 
		numpy.ndarray : Cumulative sum of the respective probability distribution 
	'''
	if arg == 'la':
		ang, len, ad, ld = anglendiff(fm, return_abs=True)
		screen_diag = int(ceil((fm.image_size[0]**2+fm.image_size[1]**2)**0.5))
		y_arg = len[0][np.roll(fm.fix==min(fm.fix),1)]
		x_arg = reshift(ang[0][np.roll(fm.fix==min(fm.fix),1)])
		bins = [range(screen_diag+1), np.linspace(-180.5,180.5,362)]
	
	elif arg == 'coo':
		indexes = fm.fix==min(fm.fix)
		y_arg = fm.y[indexes]
		x_arg = fm.x[indexes]
		bins = [range(fm.image_size[0]+1), range(fm.image_size[1]+1)]
	
	elif arg == 'len':
		trajLen = np.roll(fm.fix,1)[fm.fix==min(fm.fix)]
		val, borders = np.histogram(trajLen, bins=1000)
		cumsum = np.cumsum(val.astype(float) / val.sum())
		return cumsum, borders
	
	else:
		raise ValueError("Not a valid argument, choose from 'la', 'coo' and 'len'.")
		
	H = createHist(y_arg, x_arg, bins=bins)
	return np.cumsum(np.concatenate(H)), H.shape
	
def drawFrom(cumsum, borders=[]):
	'''
	Draws a value from a cumulative sum.
	
	Parameters: 
		cumsum : array
			Cumulative sum from which shall be drawn.
		borders : array, optional
			If given, sets the value borders for entries in the cumsum-vector.
	Returns:
		int : Index of the cumulative sum element drawn.
	'''
	if len(borders)==0:
		return (cumsum>=random.random()).nonzero()[0][0]
	else:
		return borders[(cumsum>=random.random()).nonzero()[0][0]]

def reshift(I):
	'''
	Transforms the given number element into a range of [-180, 180],
	which covers all possible angle differences. This method reshifts larger or 
	smaller numbers that might be the output of other angular calculations
	into that range by adding or subtracting 360, respectively. 
	To make sure that angular data ranges between -180 and 180 in order to be
	properly histogrammed, apply this method first.
	
	
	Parameters: 
		I : array or list or int or float
			Number or numbers that shall be reshifted.
	
	Returns:
		int or float or array : Reshifted number or numbers
	'''
	# Output -180 to +180
	if type(I)==list:
		I = np.array(I)
	
	if type(I)==np.ndarray:
		while(sum(I>180)>0 or sum(I<-180)>0):
			I[I>180] = I[I>180]-360
			I[I<-180] = I[I<-180]+360

	if type(I)==int or type(I)==np.float64 or type(I)==float or type(I)==np.float:
		while (I>180 or I<-180):
			if I > 180:
				I-=360
			if I < -180:
				I+=360
	
	return I

def spline(ad,ld,collapse=True,xdim=[-36,36]):
	'''
	Histograms amd performs a spline fit on the given data, 
	usually angle and length differences.
	
	Parameters:
		ad : array
			The data to be histogrammed along the x-axis. 
			May range from -180 to 180.
		ld : array
			The data to be histogrammed along the y-axis.
			May range from -36 to 36.
		xdim : list, optional
			Gives the range of values on the y-axis in case of the uncollapsed 
			histogram. Defaults to [-36,36].
	'''
	ld = ld[~np.isnan(ld)]
	ad = reshift(ad[~np.isnan(ad)])	
	samples = zip(ld,ad)

	if collapse: # von 0 bis 181
		e_y = np.linspace(-36.5,36.5,74)
		e_x = np.linspace(-0.5,180.5,182)
		ad = abs(ad)
		K = createHist(ld,ad)
		H = spline_base.spline_pdf(np.array(samples), e_y, e_x, nr_knots_y = 4, nr_knots_x = 10,hist=K)		

	else:
		e_x = np.linspace(-180.5,179.5,361)
		e_y = np.linspace(xdim[0],xdim[1],(xdim[1]*2)+1)
		ad[ad>179.5]-=360
		samples = zip(ld,ad)

		H = spline_base.spline_pdf(np.array(samples), e_y, e_x, nr_knots_y = 4, nr_knots_x = 10)
	return H/H.sum()

if __name__ == '__main__':
	sim = FixSim('fixmat_photos.mat')
	#sim.set_path()
	simfm = sim.sample_many(num_samples=6263)
