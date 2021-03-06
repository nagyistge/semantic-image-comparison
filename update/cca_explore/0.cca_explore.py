#!/usr/bin/python

from sklearn.cross_decomposition import PLSCanonical, PLSRegression, CCA
from pybraincompare.compare.maths import calculate_correlation
from pybraincompare.compare.mrutils import get_images_df
from pybraincompare.mr.datasets import get_standard_mask
from sklearn.preprocessing import StandardScaler
from pybraincompare.mr.transformation import *
from sklearn import linear_model
import matplotlib.pyplot as plt
from glob import glob
import pickle
import pandas
import nibabel
import numpy
import sys
import os

base = '/scratch/users/vsochat/DATA/BRAINMETA/ontological_comparison'
update = "%s/update" %base
old_results = "%s/results" %base  # any kind of tsv/result file
results = "%s/results" %update  # any kind of tsv/result file

# Images by Concepts data frame (YES including all levels of ontology)
labels_tsv = "%s/images_contrasts_df.tsv" %old_results
image_lookup = "%s/image_nii_lookup.pkl" %update
contrast_file = "%s/filtered_contrast_images.tsv" %results

# Images by Concept data frame, our X
X = pandas.read_csv(labels_tsv,sep="\t",index_col=0)

# Dictionary to look up image files (4mm)
lookup = pickle.load(open(image_lookup,"rb"))

# Get standard mask, 4mm
standard_mask=get_standard_mask(4)

# We will save data to dictionary
result = dict()

concepts = X.columns.tolist()

# We will go through each voxel (column) in a data frame of image data
image_paths = lookup.values()
mr = get_images_df(file_paths=image_paths,mask=standard_mask)
image_ids = [int(os.path.basename(x).split(".")[0]) for x in image_paths]
mr.index = image_ids

## STANDARDIZATION #########################################################################

# Images data frame with contrast info, and importantly, number of subjects
image_df = pandas.read_csv(contrast_file,sep="\t",index_col=0)
image_df.index = image_df.image_id

# We should standardize cognitive concepts before modeling
# http://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html
scaled = pandas.DataFrame(StandardScaler().fit_transform(X))
scaled.columns = X.columns
scaled.index = X.index
X = scaled
  
norm = pandas.DataFrame(columns=mr.columns)

# Normalize the image data by number of subjects
#V* = V/sqrt(S) 
for row in mr.iterrows():
    subid = row[0]
    number_of_subjects = image_df.loc[subid].number_of_subjects.tolist()
    norm_vector = row[1]/numpy.sqrt(number_of_subjects)
    norm.loc[subid] = norm_vector

del mr
   
## CCA ANALYSIS ############################################################################
# Dataset based latent variables model

# DELETE
# Let's choose a random voxel
#norm = norm.fillna(0)

output_folder = '%s/results/cca' %update
if not os.path.exists(output_folder):
    os.mkdir(output_folder)

# Try for all data
holdout = numpy.random.choice(norm.index.tolist(),5).tolist()
train = [x for x in X.index if x not in holdout and x in norm.index]
Ytrain = norm.loc[train,:]
Ytest = norm.loc[holdout,:]
Xtrain = numpy.array(X.loc[train,:]) 
Xtest = X.loc[holdout,:]

# Need a plotting funtion
def do_plot(X_train_r,Y_train_r,X_test_r,Y_test_r,output_file):
    plt.figure(figsize=(12, 8))
    plt.subplot(221)
    plt.plot(X_train_r[:, 0], Y_train_r[:, 0], "ob", label="train")
    plt.plot(X_test_r[:, 0], Y_test_r[:, 0], "or", label="test")
    plt.xlabel("x scores")
    plt.ylabel("y scores")
    plt.title('Comp. 1: X vs Y (test corr = %.2f)' %numpy.corrcoef(X_test_r[:, 0], Y_test_r[:, 0])[0, 1])
    plt.xticks(())
    plt.yticks(())
    plt.legend(loc="best")
    plt.subplot(224)
    plt.plot(X_train_r[:, 1], Y_train_r[:, 1], "ob", label="train")
    plt.plot(X_test_r[:, 1], Y_test_r[:, 1], "or", label="test")
    plt.xlabel("x scores")
    plt.ylabel("y scores")
    plt.title('Comp. 2: X vs Y (test corr = %.2f)' % numpy.corrcoef(X_test_r[:, 1], Y_test_r[:, 1])[0, 1])
    plt.xticks(())
    plt.yticks(())
    plt.legend(loc="best")
    # 2) Off diagonal plot components 1 vs 2 for X and Y
    plt.subplot(222)
    plt.plot(X_train_r[:, 0], X_train_r[:, 1], "*b", label="train")
    plt.plot(X_test_r[:, 0], X_test_r[:, 1], "*r", label="test")
    plt.xlabel("X comp. 1")
    plt.ylabel("X comp. 2")
    plt.title('X comp. 1 vs X comp. 2 (test corr = %.2f)'% numpy.corrcoef(X_test_r[:, 0], X_test_r[:, 1])[0, 1])
    plt.legend(loc="best")
    plt.xticks(())
    plt.yticks(())
    plt.subplot(223)
    plt.plot(Y_train_r[:, 0], Y_train_r[:, 1], "*b", label="train")
    plt.plot(Y_test_r[:, 0], Y_test_r[:, 1], "*r", label="test")
    plt.xlabel("Y comp. 1")
    plt.ylabel("Y comp. 2")
    plt.title('Y comp. 1 vs Y comp. 2 , (test corr = %.2f)'% numpy.corrcoef(Y_test_r[:, 0], Y_test_r[:, 1])[0, 1])
    plt.legend(loc="best")
    plt.xticks(())
    plt.yticks(())
    plt.savefig(output_file)
    plt.close()

# PLSCA
plsca = PLSCanonical(n_components=2)
plsca.fit(Xtrain, Ytrain)
# PLSCanonical(algorithm='nipals', copy=True, max_iter=500, n_components=2,
#       scale=True, tol=1e-06)
X_train_r, Y_train_r = plsca.transform(Xtrain, Ytrain)
X_test_r, Y_test_r = plsca.transform(Xtest, Ytest)
do_plot(X_train_r,Y_train_r,X_test_r,Y_test_r,'%s/PLSCA_2comp_norm.pdf' %output_folder)

# CCA
# probably not necessary, but just in case the data was modified in some way
Ytrain = norm.loc[train,:]
Ytest = norm.loc[holdout,:]
Xtrain = numpy.array(X.loc[train,:]) 
Xtest = X.loc[holdout,:]
cca = CCA(n_components=2)
cca.fit(Xtrain, Ytrain)
# CCA(copy=True, max_iter=500, n_components=2, scale=True, tol=1e-06)
X_train_r, Y_train_r = cca.transform(Xtrain, Ytrain)
X_test_r, Y_test_r = cca.transform(Xtest, Ytest)
do_plot(X_train_r,Y_train_r,X_test_r,Y_test_r,'%s/CCA_2comp_norm.pdf' %output_folder)
