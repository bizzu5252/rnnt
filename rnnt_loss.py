from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from tensorflow.python.ops.gen_array_ops import matrix_diag_part_v2
import tensorflow as tf

LOG_0 = -100.0


def extract_diagonals(log_probs):
    time_steps = tf.shape(log_probs)[1]  # T
    output_steps = tf.shape(log_probs)[2]  # U + 1
    reverse_log_probs = tf.reverse(log_probs, axis=[-1])
    paddings = [[0, 0], [0, 0], [time_steps - 1, 0]]
    padded_reverse_log_probs = tf.pad(reverse_log_probs, paddings, 'CONSTANT', constant_values=LOG_0)
    diagonals = matrix_diag_part_v2(padded_reverse_log_probs, k=(0, time_steps + output_steps - 2),
                                    padding_value=LOG_0)

    return tf.transpose(diagonals, perm=[1, 0, 2])


def transition_probs(labels, log_probs):
    blank_probs = log_probs[:, :, :, 0]
    labels = tf.one_hot(tf.tile(tf.expand_dims(tf.concat([labels, tf.zeros(shape=[labels.shape[0], 1], dtype=tf.int64)], axis=1), axis=1),
                                multiples=[1, log_probs.shape[1], 1]), depth=log_probs.shape[-1])
    truth_probs = tf.reduce_sum(tf.multiply(log_probs, labels), axis=-1)

    return blank_probs, truth_probs


def next_state(alpha, trans_probs):
    blank_probs = trans_probs[0]
    truth_probs = trans_probs[1]

    alpha_b = tf.concat([LOG_0*tf.ones(shape=[alpha.shape[0], 1]), alpha[:, :-1] + blank_probs], axis=1)
    alpha_t = tf.concat([alpha[:, :-1] + truth_probs, LOG_0*tf.ones(shape=[alpha.shape[0], 1])], axis=1)

    alpha = tf.reduce_logsumexp(tf.stack([alpha_b, alpha_t], axis=0), axis=0)
    return alpha


def rnnt_loss_and_grad(logits, labels, label_length, logit_length):
    log_probs = tf.nn.log_softmax(logits)

    initial_alpha = tf.concat([tf.zeros(shape=[labels.shape[0], 1]), tf.ones(shape=labels.shape[:2])*LOG_0], axis=1)

    blank_probs, truth_probs = transition_probs(labels, log_probs)
    trans_probs_diags = (extract_diagonals(blank_probs), extract_diagonals(truth_probs))

    fwd = tf.scan(next_state, trans_probs_diags, initializer=initial_alpha)
    alpha = tf.transpose(tf.concat([tf.expand_dims(initial_alpha, axis=0), fwd], axis=0), perm=[1, 2, 0])

    return -alpha[:, -1, -1]