from __future__ import print_function
from __future__ import division

from six.moves import xrange

import time

from ..datasets import PreprocessQueue
from .placeholder import feed_dict_with_batch
from ..pipeline.dataset import PreprocessedDataset


def train(model,
          data,
          preprocess_algorithm,
          batch_size,
          dropout,
          max_steps,
          preprocess_first=False,
          display_step=10,
          save_step=250):

    global_step = model.initialize()

    capacity = 10 * batch_size

    if preprocess_first:
        data.train = PreprocessedDataset(data.train, preprocess_algorithm)
        data.val = PreprocessedDataset(data.val, preprocess_algorithm)
        data.test = PreprocessedDataset(data.test, preprocess_algorithm)

    try:
        if not preprocess_first:
            train_queue = PreprocessQueue(
                data.train,
                preprocess_algorithm,
                batch_size,
                capacity,
                shuffle=True)

            val_queue = PreprocessQueue(
                data.val,
                preprocess_algorithm,
                batch_size,
                capacity,
                shuffle=True)

        for step in xrange(global_step, max_steps):
            t_pre = time.process_time()

            if not preprocess_first:
                batch = train_queue.dequeue()
            else:
                batch = data.train.next_batch(batch_size, shuffle=True)

            feed_dict = feed_dict_with_batch(model.placeholders, batch,
                                             dropout)
            t_pre = time.process_time() - t_pre

            t_train = model.train(feed_dict, step)

            if step % display_step == 0:
                # Evaluate on training and validation set with zero dropout.
                feed_dict.update({model.placeholders['dropout']: 0})
                if not model.isMultilabel:
                    train_loss, train_acc = model.evaluate(feed_dict)
                else:
                    train_loss, train_acc_1, train_acc_2 = model.evaluate(
                        feed_dict)

                if not preprocess_first:
                    batch = val_queue.dequeue()
                else:
                    batch = data.val.next_batch(batch_size, shuffle=True)

                feed_dict = feed_dict_with_batch(model.placeholders, batch)
                if not model.isMultilabel:
                    val_loss, val_acc = model.evaluate(feed_dict)
                else:
                    val_loss, val_acc_1, val_acc_2 = model.evaluate(feed_dict)

                log = 'step={}, '.format(step)
                if preprocess_first:
                    log += 'time={:.2f}s, '.format(t_train)
                else:
                    log += 'time={:.2f}s + {:.2f}s, '.format(t_pre, t_train)
                log += 'train_loss={:.5f}, '.format(train_loss)
                if not model.isMultilabel:
                    log += 'train_acc={:.5f}, '.format(train_acc)
                else:
                    log += 'train_top_acc={:.5f}, '.format(train_acc_1)
                    log += 'train_threshold_acc={:.5f}, '.format(train_acc_2)
                log += 'val_loss={:.5f}, '.format(val_loss)
                if not model.isMultilabel:
                    log += 'val_acc={:.5f}'.format(val_acc)
                else:
                    log += 'val_top_acc={:.5f}, '.format(val_acc_1)
                    log += 'val_threshold_acc={:.5f}'.format(val_acc_2)

                print(log)

            if step % save_step == 0:
                model.save()

    except KeyboardInterrupt:
        print()

    finally:
        if not preprocess_first:
            train_queue.close()
            val_queue.close()

    print('Optimization finished!')
    print('Evaluate on test set. This can take a few minutes.')

    try:
        if not preprocess_first:
            test_queue = PreprocessQueue(
                data.test,
                preprocess_algorithm,
                batch_size,
                capacity,
                shuffle=False)

        num_steps = data.test.num_examples // batch_size
        loss = 0
        acc_1 = 0
        acc_2 = 0

        for i in xrange(num_steps):
            if not preprocess_first:
                batch = test_queue.dequeue()
            else:
                batch = data.test.next_batch(batch_size, shuffle=False)

            feed_dict = feed_dict_with_batch(model.placeholders, batch)
            if not model.isMultilabel:
                batch_loss, batch_acc = model.evaluate(feed_dict)
                acc_1 += batch_acc
            else:
                batch_loss, batch_acc_1, batch_acc_2 = model.evaluate(
                    feed_dict)
                acc_1 += batch_acc_1
                acc_2 += batch_acc_2

            loss += batch_loss

        loss /= num_steps
        acc_1 /= num_steps
        acc_2 /= num_steps

        log = 'Test results: '
        log += 'cost={:.5f}, '.format(loss)
        if not model.isMultilabel:
            log += 'acc={:.5f}'.format(acc_1)
        else:
            log += 'top_acc={:.5f}, '.format(acc_1)
            log += 'threshold_acc={:.5f}'.format(acc_2)

        print(log)

    except KeyboardInterrupt:
        print()
        print('Test evaluation aborted.')

    finally:
        if not preprocess_first:
            test_queue.close()
