from typing import Dict

import torch
import torch.nn as nn
from torch import Tensor

from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

from nog5.base import ModelBase

from nog5.embeddings import ESM1bEmbedding


class CNNbLSTM(ModelBase):

    def __init__(self, init_n_channels: int, out_channels: int, cnn_layers: int, kernel_size: tuple, padding: tuple, n_hidden: int, dropout: float, lstm_layers: int):
        """ Baseline model for CNNbLSTM
        Args:
            init_n_channels: size of the incoming feature vector
            out_channels: amount of hidden neurons in the bidirectional lstm
            cnn_layers: amount of cnn layers
            kernel_size: kernel sizes of the cnn layers
            padding: padding of the cnn layers
            n_hidden: amount of hidden neurons
            dropout: amount of dropout
            lstm_layers: amount of bidirectional lstm layers
        """

        super().__init__()

        # CNN blocks
        self.conv = nn.ModuleList()
        for i in range(cnn_layers):
            self.conv.append(nn.Sequential(*[
                nn.Dropout(p=dropout),
                nn.Conv1d(in_channels=init_n_channels, out_channels=out_channels,
                          kernel_size=kernel_size[i], padding=padding[i]),
                nn.ReLU(),
            ]))

        self.batch_norm = nn.BatchNorm1d(init_n_channels + (out_channels * 2))

        # LSTM block
        self.lstm = nn.LSTM(input_size=init_n_channels + (out_channels * 2), hidden_size=n_hidden, batch_first=True,
                            num_layers=lstm_layers, bidirectional=True, dropout=dropout)
        self.lstm_dropout_layer = nn.Dropout(p=dropout)

        # Task block
        self.ss8 = nn.Sequential(*[
            nn.Linear(in_features=n_hidden * 2, out_features=8),
        ])
        self.dis = nn.Sequential(*[
            nn.Linear(in_features=n_hidden * 2, out_features=1),
        ])
        self.rsa = nn.Sequential(*[
            nn.Linear(in_features=n_hidden * 2, out_features=1),
        ])
        self.phi = nn.Sequential(*[
            nn.Linear(in_features=n_hidden * 2, out_features=2),
            nn.Tanh()
        ])
        self.psi = nn.Sequential(*[
            nn.Linear(in_features=n_hidden * 2, out_features=2),
            nn.Tanh()
        ])

    def forward(self, x: Tensor, seq_lengths: Tensor) -> Dict[str, Tensor]:
        """ Forwarding logic """
        max_seq_length = int(max(seq_lengths))
        x = x.permute(0, 2, 1)

        # concatenate channels from residuals and input + batch norm
        r = x
        for layer in self.conv:
            r = torch.cat([r, layer(x)], dim=1)

        x = self.batch_norm(r)

        # calculate double layer bidirectional lstm
        x = x.permute(0, 2, 1)
        x = pack_padded_sequence(x, seq_lengths, batch_first=True, enforce_sorted=False)
        x, _ = self.lstm(x)
        x, _ = pad_packed_sequence(x, total_length=max_seq_length, batch_first=True)

        x = self.lstm_dropout_layer(x)

        # hidden neurons to classes
        ss8 = self.ss8(x)
        dis = self.dis(x)
        rsa = self.rsa(x)
        phi = self.phi(x)
        psi = self.psi(x)

        return {'ss8': ss8, 'dis': dis, 'rsa': rsa, 'phi': phi, 'psi': psi}


class CNNbLSTM_ESM1b_Complete(CNNbLSTM):
    def __init__(self, init_n_channels: int, out_channels: int, cnn_layers: int, kernel_size: tuple, padding: tuple, n_hidden: int, dropout: float, lstm_layers: int, embedding_pretrained: str = None, **kwargs):
        """ Constructor
        Args:
            init_n_channels: size of the incoming feature vector
            out_channels: amount of hidden neurons in the bidirectional lstm
            cnn_layers: amount of cnn layers
            kernel_size: kernel sizes of the cnn layers
            padding: padding of the cnn layers
            n_hidden: amount of hidden neurons
            dropout: amount of dropout
            lstm_layers: amount of bidirectional lstm layers
            embedding_pretrained: path to language model weights
        """
        super().__init__(init_n_channels, out_channels, cnn_layers, kernel_size, padding, n_hidden, dropout,
                         lstm_layers)

        # ESM1b block
        self.embedding = ESM1bEmbedding(embedding_pretrained, **kwargs)

    def forward(self, x: Tensor, seq_lengths: Tensor) -> Dict[str, Tensor]:
        """ Forwarding logic """
        x = self.embedding(x, seq_lengths)

        return super()(x, seq_lengths)
