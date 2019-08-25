# -*- coding: utf-8 -*-
import os
import multiprocessing
from glob import glob

import numpy as np
from keras import backend
from keras.models import Model
from keras.optimizers import adam
from keras.layers import Flatten, Dense, Dropout
from keras.callbacks import TensorBoard, Callback
from keras.callbacks import ModelCheckpoint, ReduceLROnPlateau
# from moxing.framework import file
import json
from data_gen import data_flow
from models.resnet50 import ResNet50

backend.set_image_data_format('channels_last')


def model_fn(FLAGS, objective, optimizer, metrics):
    """
    pre-trained resnet50 model
    """
    base_model = ResNet50(weights="imagenet",
                          include_top=False,
                          pooling='avg',
                          input_shape=(FLAGS.input_size, FLAGS.input_size, 3),
                          classes=FLAGS.num_classes)
    # for layer in base_model.layers:
    #     layer.trainable = False
    x = base_model.output
    x = Dropout(0.5)(x)
    predictions = Dense(FLAGS.num_classes, activation='softmax')(x)
    model = Model(inputs=base_model.input, outputs=predictions)
    model.compile(loss=objective, optimizer=optimizer, metrics=metrics)
    return model


class LossHistory(Callback):
    def __init__(self, FLAGS):
        super(LossHistory, self).__init__()
        self.FLAGS = FLAGS

    def on_train_begin(self, logs={}):
        self.losses = []
        self.val_losses = []
        self.val_accs = []
        self.files = []
        self.best_file = None

    def on_epoch_end(self, epoch, logs={}):
        self.losses.append(logs.get('loss'))
        self.val_losses.append(logs.get('val_loss'))
        self.val_accs.append(logs.get('val_acc'))

        save_path = os.path.join(self.FLAGS.train_local, 'weights_%03d_%.4f.h5' % (epoch, logs.get('val_acc')))
        self.files.append(save_path)
        self.model.save_weights(save_path)
        print('save weights file', save_path)

        self.best_file = self.files[np.argmax(np.array(self.val_accs))]

        if self.FLAGS.keep_weights_file_num > -1:
            weights_files = glob(os.path.join(self.FLAGS.train_local, '*.h5'))
            if len(weights_files) >= self.FLAGS.keep_weights_file_num:
                weights_files.sort(key=lambda file_name: os.stat(file_name).st_ctime, reverse=True)
                for file_path in weights_files[self.FLAGS.keep_weights_file_num:]:
                    if file_path==self.best_file:
                        continue
                    os.remove(file_path)  # only remove weights files on local path


def train_model(FLAGS):
    # data flow generator
    train_sequence, validation_sequence = data_flow(FLAGS.data_local, FLAGS.batch_size,
                                                    FLAGS.num_classes, FLAGS.input_size)

    optimizer = adam(lr=FLAGS.learning_rate)#, clipnorm=0.001)
    reduce_on_plateau = ReduceLROnPlateau(monitor="val_acc", mode="max", factor=0.1, patience=10, verbose=1)
    objective = 'categorical_crossentropy'
    metrics = ['accuracy']
    model = model_fn(FLAGS, objective, optimizer, metrics)
    if not os.path.exists(FLAGS.train_local):
        os.makedirs(FLAGS.train_local)
    tensorBoard = TensorBoard(log_dir=FLAGS.train_local)
    history = LossHistory(FLAGS)
    model.fit_generator(
        train_sequence,
        steps_per_epoch= len(train_sequence),
        epochs=FLAGS.max_epochs,
        verbose=2,
        callbacks=[history, tensorBoard,reduce_on_plateau],
        validation_data=validation_sequence,
        max_queue_size=10,
        workers=int(multiprocessing.cpu_count() * 0.7),
        use_multiprocessing=True,
        shuffle=True
    )

    print('training done!')

    model.load_weights(history.best_file)

    if FLAGS.deploy_script_path != '':
        from save_model import save_pb_model
        save_pb_model(FLAGS, model)

    labels = []
    logits = []

    for i in range(len(validation_sequence)):
        test_data, test_label = validation_sequence[i]
        predictions = model.predict(test_data, verbose=0)
        labels.extend(np.argmax(test_label,axis=1))
        logits.extend(np.argmax(predictions,axis=1))

    labels = np.array(labels)
    logits = np.array(logits)

    accuracy = np.sum((labels-logits)==0) / labels.size
    print('accuracy: %0.4f' % accuracy)

    result = []

    for i in range(FLAGS.num_classes):
        result.append(np.sum(((labels-logits)==0)*(labels==i)) / np.sum(labels==i))

    with open('result.json','w') as fp:
        json.dump([result,labels.tolist(), logits.tolist()],fp)

