# -*- coding: utf-8 -*-

"""NNFirst.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1TSMnd73DzczjZ5-hgFj60PWYrBIUYBxD

Author
vokrut--42Robotics
"""

# Commented out IPython magic to ensure Python compatibility.
#Import required frameworks

import math

from IPython import display
from matplotlib import cm
from matplotlib import gridspec
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from sklearn import metrics
import datetime
# %tensorflow_version 1.x
# %load_ext tensorboard
import tensorflow as tf
from tensorflow.python.data import Dataset
from pandas.io.json import json_normalize
import json


from google.colab import drive
drive.mount('/content/drive')

#upload json data file 
quantum_data = pd.read_json("drive/My Drive/qc/01/3125_random_5_qubit_circuits.json",
                            orient='records', lines=True, precise_float="precise_float")

#quantum_data.head(5)

def gate_data_preproc(quantum_data: dict,
                      gate_num: int) -> pd.DataFrame:
  """
  Function takes the raw data as a .json file, split the data into two parts, 
  the first 32 columns represent state vectors; the last 173 columns represent
  the parameters of each gate.

  Parameters: quantum_data: dict - the raw data read from .json file
              gate_num: int - current gate number from the range from  1 to 40
  Returns:    a new pandas dataframe with separated values of the statevectors and
              gate's parameters

  """
  # Since we care only about the value of the angles in U3 Gate, 
  # check for this type of gate;
  # if the gate is not a U3 gate, set the angle values to 0.
  is_not_u3gate = lambda data: data["Gate_Type"] != 'U3Gate'
  norm_data = json_normalize(quantum_data)
  
  #create new data table
  dataframe = pd.DataFrame()  

  #.loc[] - accesses a group of rows and columns by label(s) or a boolean array.
  norm_data.loc[(is_not_u3gate(norm_data), 'Angle_1')] = 0.0
  norm_data.loc[(is_not_u3gate(norm_data), 'Angle_2')] = 0.0
  norm_data.loc[(is_not_u3gate(norm_data), 'Angle_3')] = 0.0

  #iterate through each subcategory, pass if GateType or GateNumber
  #store in the new table 
  for key in norm_data:
    # print(key)
    if key == 'Gate_Number' or key == 'Gate_Type':
      continue
    dataframe[key+gate_num] = norm_data[key]
    if key in ['Target', 'Control']:
      dataframe[key+gate_num] += 1
      # print(dataframe[key+gate_num])

  return dataframe


norm_qdata = json_normalize(quantum_data['statevector'])
# print(qdata.head())
#iterate in data set. where key represent a gate number on each iteration
for key in quantum_data:
  # print(key)
  if "gate" in key:                   #if key == gate, store the gate number
    gate_num = "_" + str(key[-2:])
    gate_dataframe = gate_data_preproc(quantum_data[key], gate_num)
    norm_qdata = norm_qdata.join(gate_dataframe)

#randomize data
# norm_qdata = norm_qdata.reindex(
#     np.random.permutation(norm_qdata.index))
norm_qdata
# display.display(norm_qdata)

#analyze features
print(norm_qdata.columns)

#describe data
norm_qdata.describe()

def preprocess_features(quantum_data: pd.DataFrame) -> pd.DataFrame:
  """
  Define and store the input features.
  Parameters:   normalized dataframe
  Returns:      features, e.g. last 173 colums of the dataframe as a pandas
                dataframe type
  """
  selected_features = quantum_data.filter(regex='^(?!state)', axis=1)
  return selected_features


def preprocess_targets(quantum_data: pd.DataFrame) -> pd.DataFrame:
  """
  Define and store the targets
  Parameters:   normalized dataframe
  Returns:      targets, e.g. first 32 colums of the dataframe as a Pandas
                Dataframe object
  """
  output_targets = pd.DataFrame()
  output_targets = quantum_data.filter(regex='^state', axis=1) 
  output_targets /= 1024
  return output_targets

def preprocess_feature_labels(quantum_data):
  feature = reprocess_features(quantum_data)
  labels = reprocess_targets(quantum_data)
  return (feature, labels)

#display to male sure you are thinking correct
#display.display(preprocess_features(norm_qdata))
#display.display(preprocess_targets(norm_qdata))

#Set training data.
training_feature = preprocess_features(norm_qdata.head(2185))
training_target = preprocess_targets(norm_qdata.head(2185))

#Set valiation data.
validating_feature = preprocess_features(norm_qdata.tail(100))
validating_target = preprocess_targets(norm_qdata.tail(100))


#displays features and targets
# print("Training feature")
# display.display(training_feature)

# print("Training targets")
# display.display(training_target)

# print("Validating data")
# display.display(validating_feature)

def construct_feature_columns(input_features):
  """
  Construct the TensorFlow Feature Columns.
  Parameters: input_features: The names of the numerical input features to use.
  Returns: A set of feature columns
  """
  return set([tf.feature_column.numeric_column(my_feature)
              for my_feature in input_features])

def create_training_input_fn(features, labels, batch_size, num_epochs=None, shuffle=True):

  """
    A custom input_fn for sending qauntum data to the estimator for training.
  Parameters:
    features: The training features.
    labels: The training labels.
    batch_size: Batch size to use during training.
    num_epochs: number of epochs
  Returns:
    A function that returns batches of training features and labels during
    training.
  """

  def _input_fn(num_epochs=None, shuffle=True):
    # Input pipelines are reset with each call to .train(). To ensure model
    # gets a good sampling of data, even when number of steps is small, we 
    # shuffle all the data before creating the Dataset object

    raw_features = {key:np.array(value) for key, value in dict(features).items()}
    # print(raw_features)
    raw_targets = np.array(labels)
   
    ds = Dataset.from_tensor_slices((raw_features,raw_targets)) # warning: 2GB limit
    ds = ds.batch(batch_size).repeat(num_epochs)
    
    if shuffle:
      ds = ds.shuffle(10000)
    
    # Return the next batch of data.
    feature_batch, label_batch = ds.make_one_shot_iterator().get_next()
    return feature_batch, label_batch

  return _input_fn

def create_predict_input_fn(features, targets, batch_size):
  """
  A custom input function for sending qauntum data to the estimator for predictions.
  Parameters:
    features: The features to base predictions on.
    labels: The labels of the prediction examples.
    batch_size: size of the taken batch
  Returns:
    features and labels for predictions.
  """
  def _input_fn():
    raw_features = {key:np.array(value) for key, value in dict(features).items()}
    # print(raw_features)
    raw_targets = np.array(targets)
    
    ds = Dataset.from_tensor_slices((raw_features, raw_targets)) # warning: 2GB limit
    ds = ds.batch(batch_size)
    
        
    # Return the next batch of data.
    feature_batch, label_batch = ds.make_one_shot_iterator().get_next()
    return feature_batch, label_batch

  return _input_fn

def my_log_error_fn(predict, actual):
  """
    Custom logloss function
  """

  raws = len(predict)
  col = predict.shape[1]
  it = np.nditer([predict, actual])
  err = 0.0
  with it:
    for (x, y) in it:
      err += (y*np.log(x) + (1 - y)*np.log(1 - x))

  return -err / ( col * raws)

# Clear any logs from previous runs
!rm -rf ./logs/

# directory for tensorboard data
MODEL_DIR= 'logs'

tf.compat.v1.summary.FileWriterCache.clear()

def train_nn_classification_model(
    learning_rate,
    steps,
    batch_size,
    hidden_units,
    training_examples,
    training_targets,
    validation_examples,
    validation_targets):
  
  """
    Trains a neural network regression model for the qauntum dataset.
  In addition to training, this function also prints training progress information,
  a plot of the training and validation loss over time.
  Parameters:
    learning_rate: A `float`, the learning rate to use.
    steps: A non-zero `int`, the total number of training steps. A training step
           consists of a forward and backward pass using a single batch.
    batch_size: A non-zero `int`, the batch size.
    hidden_units: A `list` of int values, specifying the number of neurons in each layer.
    training_examples: A `DataFrame` containing the training features.
    training_targets: A `DataFrame` containing the training labels.
    validation_examples: A `DataFrame` containing the validation features.
    validation_targets: A `DataFrame` containing the validation labels.
  Returns:
    The trained `DNNRegresion` object.
  """

  periods = 10
  # Caution: input pipelines are reset with each call to train. 
  # If the number of steps is small, your model may never see most of the data.  
  # So with multiple `.train` calls like this you may want to control the length 
  # of training with num_epochs passed to the input_fn. Or, you can do a really-big shuffle, 
  # or since it's in-memory data, shuffle all the data in the `input_fn`.
  steps_per_period = steps / periods  
  
  # Create the input functions.
  predict_training_input_fn = create_predict_input_fn(
    training_examples, training_targets, batch_size)
  
  predict_validation_input_fn = create_predict_input_fn(
    validation_examples, validation_targets, batch_size)
  
  #training input function
  training_input_fn = create_training_input_fn(
    training_examples, training_targets, batch_size)
  
  # Create feature columns using customs function
  feature_columns = construct_feature_columns(training_examples)
  #set the optimiser
  my_optimizer = tf.train.AdagradOptimizer(learning_rate=learning_rate)
  my_optimizer = tf.contrib.estimator.clip_gradients_by_norm(my_optimizer, 5.0)



  """  hidden_units: Iterable of number hidden units per layer.
                  All layers are fully connected. Ex. [64, 32] means first
                  layer has 64 nodes and second one has 32.
  feature_columns: An iterable containing all the feature columns used by the model.
                   All items in the set should be instances of classes derived from _FeatureColumn.
  model_dir: Directory to save model parameters, graph and etc.
             This can also be used to load checkpoints from the directory into a estimator to continue training a previously saved model.
  label_dimension: Number of regression targets per example.
                  This is the size of the last dimension of the labels and logits Tensor objects (typically, these have shape [batch_size, label_dimension]).
  weight_column: A string or a _NumericColumn created by tf.feature_column.numeric_column
                defining feature column representing weights. It is used to down weight or boost examples during training.
                It will be multiplied by the loss of the example. If it is a string, it is used as a key to fetch weight tensor from the features.
                If it is a _NumericColumn, raw tensor is fetched by key weight_column.key, then weight_column.normalizer_fn is applied on it to get weight tensor.
  optimizer: An instance of tf.keras.optimizers.Optimizer used to train the model.
             Can also be a string (one of 'Adagrad', 'Adam', 'Ftrl', 'RMSProp', 'SGD'), or callable. Defaults to Adagrad optimizer.
  activation_fn: Activation function applied to each layer. If None, will use tf.nn.relu.
  dropout: When not None, the probability we will drop out a given coordinate.
  config: RunConfig object to configure the runtime settings.
  warm_start_from: A string filepath to a checkpoint to warm-start from, or a WarmStartSettings object
                    to fully configure warm-starting. If the string filepath is provided instead of a WarmStartSettings,
                    then all weights are warm-started, and it is assumed that vocabularies and Tensor names are unchanged.
  loss_reduction: One of tf.losses.Reduction except NONE. Describes how to reduce training loss over batch. Defaults to SUM_OVER_BATCH_SIZE.
  batch_norm: Whether to use batch normalization after each hidden layer.

  Create a DNNRegression object.
  Use .train(trainig_data) to train the model
  use .predict(predict_training_function) to make a prediction using a model
  """
  classifier = tf.estimator.DNNEstimator(
      head=tf.contrib.estimator.multi_label_head(n_classes=32),
      hidden_units=hidden_units,
      feature_columns=feature_columns,
      model_dir=MODEL_DIR,
      optimizer=my_optimizer,
      # config=tf.contrib.learn.RunConfig(keep_checkpoint_max=1)
      config=tf.estimator.RunConfig(model_dir=MODEL_DIR, save_summary_steps=100)
  )

  # Train the model, but do so inside a loop so that we can periodically assess
  # loss metrics.
  print("Training model...")
  print("LogLoss error (on validation data):")
  training_errors = []
  validation_errors = []
  for period in range (0, periods):
    # Train the model, starting from the prior state.
    print("Period = ", period)
    classifier.train(
        input_fn=training_input_fn,
        steps=steps_per_period,
    )
  
    classifier.evaluate(input_fn=predict_validation_input_fn)

  return classifier

#the best parameters I've discovered by this time 
# learning_rate=0.003,
    # steps=1000,
    # batch_size=32,
    # hidden_units=[1024, 512, 256],

model = train_nn_classification_model(
    learning_rate=0.001,
    steps=1000,
    batch_size=32,
    hidden_units=[1024, 512, 256],
    training_examples=training_feature,
    training_targets=training_target,
    validation_examples=validating_feature,
    validation_targets=validating_target)

tensorboard --logdir logs/

def my_input_fn(features, targets, batch_size=1,  shuffle=True, num_epochs=None):
  features = {key:np.array(value) for key, value in dict(features).items()}
  #  print(raw_features)
  # raw_targets = np.array(labels)
   
  ds = Dataset.from_tensor_slices((features, targets)) # warning: 2GB limit
  ds = ds.batch(batch_size).repeat(num_epochs)
    
  if shuffle:
    ds = ds.shuffle(10000)
    
  # Return the next batch of data.
  features, labels = ds.make_one_shot_iterator().get_next()  
  return features, labels

#Evaluate the model

quantum_test_data = pd.read_json("drive/My Drive/qc/02/3125_random_5_qubit_circuits.json",
                            orient='records', lines=True, precise_float="precise_float")

norm_test_qdata = json_normalize(quantum_test_data['statevector'])
#iterate in data set. where key represent a gate number on each iteration
for key in quantum_test_data:
  # print(key)
  if "gate" in key:                   #if key == gate, store the gate number
    gate_num = "_" + str(key[-2:])
    gate_dataframe = gate_data_preproc(quantum_test_data[key], gate_num)
    norm_test_qdata = norm_test_qdata.join(gate_dataframe)

#randomize data
# norm_qdata = norm_qdata.reindex(
#     np.random.permutation(norm_qdata.index))
norm_test_qdata

test_examples = preprocess_features(norm_test_qdata.head(100))
test_targets = preprocess_targets(norm_test_qdata.head(100))

predict_testing_input_fn = lambda: my_input_fn(test_examples, 
                                               test_targets, 
                                               num_epochs=1, 
                                               shuffle=False)

test_predictions = model.predict(input_fn=predict_testing_input_fn)
test_predictions = np.array([item['probabilities'] for item in test_predictions]) 

log_loss = my_log_error_fn(test_predictions, test_targets)

print("Final Log Loss (on test data): %0.2f" % log_loss)

#Predict the model
quantum_test_data = pd.read_json("drive/My Drive/qc/02/3125_random_5_qubit_circuits.json",
                            orient='records', lines=True, precise_float="precise_float")

norm_test_qdata = json_normalize(quantum_test_data['statevector'])
#iterate in data set. where key represent a gate number on each iteration
for key in quantum_test_data:
  # print(key)
  if "gate" in key:                   #if key == gate, store the gate number
    gate_num = "_" + str(key[-2:])
    gate_dataframe = gate_data_preproc(quantum_test_data[key], gate_num)
    norm_test_qdata = norm_test_qdata.join(gate_dataframe)

#randomize data
# norm_qdata = norm_qdata.reindex(
#     np.random.permutation(norm_qdata.index))
norm_test_qdata

def input_fn(features, batch_size=256):
    """An input function for prediction."""
    # Convert the inputs to a Dataset without labels.
    return tf.data.Dataset.from_tensor_slices(dict(features)).batch(batch_size)

predict_features = preprocess_features(norm_test_qdata.tail(1))
actual_targets = preprocess_targets(norm_test_qdata.tail(1))

predict1_fn = lambda: input_fn(predict_features, batch_size = 256)

predictions = model.predict(input_fn=predict1_fn)
print(type(actual_targets))
i=0
for predict in predictions:
  print([predict['probabilities'][i] for i in range(32)])

display.display(actual_targets)

# test_predictions = np.array([item['probabilities'] for item in test_predictions]) 

# log_loss = my_log_error_fn(test_predictions, test_targets)

# print("Final Log Loss (on test data): %0.2f" % log_loss)
