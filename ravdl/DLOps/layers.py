import ravop as R
import numpy as np
import math
from .utils.data_operations import determine_padding

class Layer(object):

    def set_input_shape(self, shape):
        """ Sets the shape that the layer expects of the input in the forward
        pass method """
        self.input_shape = shape

    def set_layer_name(self, name=None):
        """ Sets the name of the layer. """
        if name is not None:
            self.layer_name = name
        else:
            self.layer_name = self.__class__.__name__

    def get_layer_name(self):
        """ The name of the layer. Used in model summary. """
        return self.layer_name

    def parameters(self):
        """ The number of trainable parameters used by the layer """
        return 0

    def output_shape(self):
        """ The shape of the output produced by forward_pass """
        raise NotImplementedError()


class Dense(Layer):
    def __init__(self, n_units, input_shape=None):
        self.forward_pass = None
        self.backward_pass = None
        self.n_units = n_units
        self.layer_input = None
        self.input_shape = input_shape
        self.trainable = True

    def initialize(self, optimizer):
        self.optimizer = optimizer
        np_limit = 1 / math.sqrt(self.input_shape[0])
        self.np_W  = np.random.uniform(-np_limit, np_limit, (self.input_shape[0], self.n_units))
        self.np_w0 = np.zeros((1, self.n_units))

    def parameters(self): 
        return np.prod(self.np_W.shape) + np.prod(self.np_w0.shape)

    def _forward_pass(self, X, input_layer = "False", training=True):
        self.layer_input = X
        self.forward_pass = R.forward_pass_dense(
            X, n_units=self.n_units, input_shape = self.input_shape, data = self.backward_pass, input_layer = input_layer
        )
        return self.forward_pass

    def _backward_pass(self, loss_grad, input_layer = "False"):
        if self.trainable:
            self.backward_pass = R.backward_pass_dense(
                loss_grad, layer_input = self.layer_input, optimizer = self.optimizer.data_dict(), data = self.forward_pass, input_layer = input_layer
            )
        return self.backward_pass

    def output_shape(self):
        return (self.n_units, )

    def persist_weights(self):
        self.forward_pass.persist_op("{}_forward_pass".format(self.layer_name))
        self.backward_pass.persist_op("{}_backward_pass".format(self.layer_name))

class BatchNormalization(Layer):
    """Batch normalization.
    """
    def __init__(self, momentum=0.99, epsilon=1e-2):
        self.momentum = momentum
        self.float_momentum = momentum
        self.trainable = True
        self.eps = epsilon
        self.float_eps = epsilon
        self.running_mean = None
        self.running_var = None
        self.forward_pass = None
        self.backward_pass = None

    def initialize(self, optimizer):
        # Initialize the parameters
        self.optimizer = optimizer

        if len(self.input_shape) == 1:
            shape = (1, self.input_shape[0])
        else:
            shape = (1,self.input_shape[0], 1,1)
        # np equivalent for summary params
        self.np_gamma = np.ones(shape)
        self.np_beta = np.zeros(shape)

    def parameters(self):
        return np.prod(self.np_gamma.shape) + np.prod(self.np_beta.shape)        

    def _forward_pass(self, X, input_layer="False", training=True):

        if training:
            training="True"
        else:
            training = "False"

        if self.trainable:
            trainable="True"
        else:
            trainable="False"


        self.forward_pass = R.forward_pass_batchnorm(
            X, input_shape=self.input_shape,
            momentum = self.momentum, eps = self.eps,
            training=training, trainable=trainable, 
            data = self.backward_pass,
            input_layer=input_layer
        )

        return self.forward_pass

    def _backward_pass(self, accum_grad, input_layer="False"):

        # Save parameters used during the forward pass
        if self.trainable:
            trainable = "True"

        self.backward_pass = R.backward_pass_batchnorm(
            accum_grad,
            input_shape = self.input_shape,
            optimizer = self.optimizer.data_dict(),
            trainable=trainable,
            data = self.forward_pass,
            input_layer = input_layer
        )

        return self.backward_pass

    def output_shape(self):
        return self.input_shape

    def persist_weights(self):
        self.forward_pass.persist_op("{}_forward_pass".format(self.layer_name))
        self.backward_pass.persist_op("{}_backward_pass".format(self.layer_name))

class Dropout(Layer):
    """A layer that randomly sets a fraction p of the output units of the previous layer
    to zero.

    Parameters:
    -----------
    p: float
        The probability that unit x is set to zero.
    """
    def __init__(self, p=0.2):
        self.p = p
        self._mask = None
        self.input_shape = None
        self.n_units = None
        self.pass_through = True
        self.trainable = True
        self.forward_pass = None
        self.backward_pass = None

    def _forward_pass(self, X, training=True, input_layer="False"):
        # c = g.one - self.p
        if training:
            training = "True"
        else:
            training = "False"

        self.forward_pass = R.forward_pass_dropout(X, p = self.p, training=training, input_layer = input_layer)
        return self.forward_pass

    def _backward_pass(self, accum_grad, input_layer="False"):
        self.backward_pass = R.backward_pass_dropout(accum_grad, data = self.forward_pass, input_layer = input_layer)
        return self.backward_pass

    def output_shape(self):
        return self.input_shape

    def persist_weights(self):
        pass

    def save_weights(self):
        self.p.persist_op(self.get_layer_name() + "_p")


class Activation(Layer):
    """A layer that applies an activation operation to the input.

    Parameters:
    -----------
    name: string
        The name of the activation function that will be used.
    """

    def __init__(self, name):
        self.activation_name = name
        self.trainable = True
        self.forward_pass = None
        self.backward_pass = None
        

    # def layer_name(self):
    #     return "Activation (%s)" % (self.activation_func.__class__.__name__)

    def _forward_pass(self, X, training=True, input_layer = "False"):
        self.layer_input = X
        self.forward_pass = R.forward_pass_activation(X, act_data = str({'name':self.activation_name}), input_layer = input_layer)
        return self.forward_pass

    def _backward_pass(self, accum_grad, input_layer="False"):
        self.backward_pass = R.backward_pass_activation(accum_grad, layer_input = self.layer_input, act_data = str({'name':self.activation_name}), input_layer = input_layer)
        return self.backward_pass

    def output_shape(self):
        return self.input_shape

    def persist_weights(self):
        pass

class Conv2D(Layer):

    def __init__(self, n_filters, filter_shape, input_shape=None, padding='same', stride=1):
        self.n_filters = n_filters
        self.filter_shape = filter_shape
        self.padding = padding
        self.stride = stride
        self.input_shape = input_shape
        self.trainable = True
        self.W = None
        self.w0 = None
        self.forward_pass = None
        self.backward_pass = None

    def initialize(self, optimizer):
        self.optimizer = optimizer

        # Initialize the weights
        filter_height, filter_width = self.filter_shape
        channels = self.input_shape[0]

        # equivalent for summary params
        np_limit = 1 / math.sqrt(np.prod(self.filter_shape))
        self.np_W  = np.random.uniform(-np_limit, np_limit, size=(self.n_filters, channels, filter_height, filter_width))
        self.np_w0 = np.zeros((self.n_filters, 1))

    def parameters(self):
        return np.prod(self.np_W.shape) + np.prod(self.np_w0.shape)

    def _forward_pass(self, X, input_layer="False", training=True):
        self.layer_input = X
        self.forward_pass = R.forward_pass_conv2d(
            X,
            input_shape = self.input_shape, 
            n_filters = self.n_filters, filter_shape = self.filter_shape, stride = self.stride, padding_data=str({'padding':self.padding}),
            data = self.backward_pass, 
            input_layer = input_layer
        )
        return self.forward_pass 


    def _backward_pass(self, accum_grad, input_layer = "False"):
        # Reshape accumulated gradient into column shape
        if self.trainable:
            trainable = "True"
        else:
            trainable = "False"

        self.backward_pass = R.backward_pass_conv2d(accum_grad,
            layer_input = self.layer_input,
            n_filters = self.n_filters, filter_shape = self.filter_shape, stride = self.stride, padding_data=str({'padding':self.padding}),
            optimizer = self.optimizer.data_dict(),
            data = self.forward_pass,
            trainable = trainable,
            input_layer=input_layer
        )

        return self.backward_pass

    def output_shape(self):
        channels, height, width = self.input_shape
        pad_h, pad_w = determine_padding(self.filter_shape, output_shape=self.padding)
        output_height = (height + np.sum(pad_h) - self.filter_shape[0]) / self.stride + 1
        output_width = (width + np.sum(pad_w) - self.filter_shape[1]) / self.stride + 1
        return self.n_filters, int(output_height), int(output_width)

    def persist_weights(self):
        self.forward_pass.persist_op("{}_forward_pass".format(self.layer_name))
        self.backward_pass.persist_op("{}_backward_pass".format(self.layer_name))

class Flatten(Layer):
    """ Turns a multidimensional matrix into two-dimensional """
    def __init__(self, input_shape=None):
        self.prev_shape = None
        self.trainable = True
        self.input_shape = input_shape
        self.forward_pass = None
        self.backward_pass = None

    def _forward_pass(self, X, training=True, input_layer = "False"):
        self.prev_input = X
        self.forward_pass = R.forward_pass_flatten(X, input_layer = input_layer)
        return self.forward_pass

    def _backward_pass(self, accum_grad, input_layer = "False"):
        self.backward_pass = R.backward_pass_flatten(accum_grad, prev_input = self.prev_input, input_layer = input_layer)
        return self.backward_pass

    def output_shape(self):
        return (int(np.prod(self.input_shape)),)

    def persist_weights(self):
        pass

class MaxPooling2D(Layer):
    """A parent class of MaxPooling2D and AveragePooling2D
    """
    def __init__(self, pool_shape=(2, 2), stride=1, padding="same"):
        self.pool_shape = pool_shape
        self.stride = stride
        self.padding_data = {'padding': padding}
        self.trainable = True
        self.forward_pass = None
        self.backward_pass = None

    def _forward_pass(self, X, training=True, input_layer = "False"):

        self.forward_pass = R.forward_pass_maxpool2d(
            X,
            input_shape = self.input_shape, 
            pool_shape = self.pool_shape, stride = self.stride, padding_data = str(self.padding_data),
            input_layer = input_layer
        )

        return self.forward_pass

    def _backward_pass(self, accum_grad, input_layer = "False"):
        # batch_size, _, _, _ = accum_grad().shape

        self.backward_pass = R.backward_pass_maxpool2d(
            accum_grad, 
            input_shape = self.input_shape, 
            pool_shape = self.pool_shape, stride = self.stride, 
            padding_data = str(self.padding_data),
            data = self.forward_pass,
            input_layer = input_layer
        )

        return self.backward_pass

    def output_shape(self):
        channels, height, width = self.input_shape
        out_height = (height - self.pool_shape[0]) / self.stride + 1
        out_width = (width - self.pool_shape[1]) / self.stride + 1
        assert out_height % 1 == 0
        assert out_width % 1 == 0
        return channels, int(out_height), int(out_width)