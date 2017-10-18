import tensorflow as tf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pandas_datareader.data as web
import datetime
import time

# Disable UserWarning: export TF_CPP_MIN_LOG_LEVEL=2


def get_date():
    return str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y%m%d'))


def rsi_function(prices, n=14):
    deltas = np.diff(prices)
    seed = deltas[:n + 1]
    up = seed[seed >= 0].sum()/n
    down = -seed[seed < 0].sum()/n
    relative_strengh = up/down
    rsi = np.zeros_like(prices)
    rsi[:n] = 100. - 100./(1. + relative_strengh)

    for i in range(n, len(prices)):
        delta = deltas[i - 1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta

        up = (up * (n - 1) + upval)/n
        down = (down * (n - 1) + downval)/n

        relative_strengh = up/down
        rsi[i] = 100. - 100. / (1. + relative_strengh)

    return rsi


def stochastics_oscillator(df, period):
    l, h = pd.DataFrame.rolling(df, period).min(), pd.DataFrame.rolling(df, period).max()
    return 100 * (df - l) / (h - l)


def ATR(df, period):
    df['H-L'] = abs(df['High'] - df['Low'])
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    return df[['H-L', 'H-PC', 'L-PC']].max(axis=1).to_frame()


## 0) *** Download data and calculate indicators ***
# Tesla:
ticker = 'TSLA'

# SP500:
# ticker = '^GSPC'

start_date = '20000101'
end_date = get_date()

# (exponential) moving averages:
m_av_1 = 100
m_av_2 = 200

main_df = web.DataReader('TSLA', 'yahoo', start_date, end_date)
main_df.index.names = ['date']

print(len(main_df.index))

# ...

# ...

# Parameters
batch_size = 3
test_dataset_size = 0.1 # = 10 percent of the complete dataset for testing
number_of_features = 4
num_units = 12
learning_rate = 0.001
epochs = 20

## 1) *** Prepare the data ***

data = pd.read_csv(ticker + '_technical_indicators.csv')
data = data.set_index(['Date'])
data_length = len(data.index) - (len(data.index) % batch_size)
data = (data - data.mean()) / (data.max() - data.min())[:data_length]

dataset_train_length = data_length - int(len(data.index) * test_dataset_size)
dataset_train_x = data[['Close', 'MACD', 'Stochastics', 'ATR']].as_matrix()[:dataset_train_length]
dataset_train_y = data['CloseTarget'].as_matrix()[:dataset_train_length]

dataset_test_x = data[['Close', 'MACD', 'Stochastics', 'ATR']].as_matrix()[dataset_train_length:]
dataset_test_y = data['CloseTarget'].as_matrix()[dataset_train_length:]

## 2) *** Build the network ***

plh_batch_x = tf.placeholder(dtype=tf.float32,
	shape=[None, batch_size, number_of_features], name='plc_batch_x')

plh_batch_y = tf.placeholder(dtype=tf.float32,
	shape=[None, batch_size, 1], name='plc_batch_x')


labels_series = tf.unstack(plh_batch_y, axis=1)

cell = tf.contrib.rnn.BasicRNNCell(num_units=num_units)

states_series, current_state = tf.nn.dynamic_rnn(cell=cell, inputs=plh_batch_x, dtype=tf.float32)
states_series = tf.transpose(states_series, [1, 0, 2])

last_state = tf.gather(params=states_series, indices=states_series.get_shape()[0] - 1)
last_label = tf.gather(params=labels_series, indices=len(labels_series) - 1)

weight = tf.Variable(tf.truncated_normal([num_units, 1]))
bias = tf.Variable(tf.constant(0.1, shape=[1]))

prediction = tf.matmul(last_state, weight) + bias

loss = tf.reduce_mean(tf.squared_difference(last_label, prediction))

train_step = tf.train.AdamOptimizer(learning_rate=learning_rate).minimize(loss)

l_loss = []
l_test_pred = []


with tf.Session() as sess:
    tf.global_variables_initializer().run()

    ## 3) Train the network

    for i_epochs in range(epochs):
        print('Epoch: {}'.format(i_epochs))

        for i_batch in range(dataset_train_length / batch_size):
            i_batch_start = i_batch * batch_size
            i_batch_end = i_batch_start + batch_size

            x = dataset_train_x[i_batch_start:i_batch_end, :].reshape(1, batch_size, number_of_features)
            y = dataset_train_y[i_batch_start:i_batch_end].reshape(1, batch_size, 1)

            feed = {plh_batch_x: x, plh_batch_y: y}

            _loss, _train_step, _pred, _last_label, _prediction = sess.run(
                            fetches=[loss, train_step, prediction, last_label, prediction],
                            feed_dict=feed)

            l_loss.append(_loss)

            # if i_batch % 100 == 0:
                # print('Batch: {} ({}-{}), loss: {}'.format(i_batch, i_batch_start, i_batch_end, _loss))

    ## 4) Test the Network

    for i_test in range(data_length - dataset_train_length - batch_size):

        # if i_batch % 30 == 0:
            # print('Test: {} ({}-{})'.format(i_test, i_test, i_test + batch_size))

        x = dataset_test_x[i_test:i_test + batch_size, :].reshape((1, batch_size, number_of_features))
        y = dataset_test_y[i_test:i_test + batch_size].reshape((1, batch_size, 1))

        feed = {plh_batch_x: x, plh_batch_y: y}

        _last_state, _last_label, test_pred = sess.run([last_state, last_label, prediction], feed_dict=feed)
        l_test_pred.append(test_pred[-1][0])  # The last one


## 5) Draw graph

fig = plt.figure(facecolor='#000606')
plt.suptitle(ticker, color='#00decc')

ax_price = plt.subplot2grid((4, 4), (0, 0), rowspan=4, colspan=4, facecolor='#000606')
ax_price.set_title(ticker)
ax_price.grid(linestyle='dotted')

ax_price.yaxis.label.set_color('#00decc')
ax_price.plot(dataset_test_y, label='Price', color='#00decc', linewidth=0.5)
ax_price.plot(l_test_pred, label='Predicted', color='#f600ff', linewidth=0.5)
ax_price.legend(loc='upper left')
ax_price.spines['bottom'].set_color('#037f7a')
ax_price.spines['left'].set_color('#037f7a')
ax_price.tick_params(axis='y', colors='#037f7a')

plt.show()
