import math
from typing import Dict

import torch
import torch.nn as nn
from torch import Tensor

from nog5.base import ModelBase
from nog5.embeddings import ESM1bEmbedding


# from https://pytorch.org/tutorials/beginner/transformer_tutorial.html
class PositionalEncoding(nn.Module):
    """ Injects some information about the relative or absolute position of the tokens in the sequence """

    def __init__(self, d_model: int, dropout: float = 0.1, max_len: int = 5000):
        """ Constructor
        Args:
            d_model: size of the incoming feature vector
            dropout: amount of hidden neurons in the bidirectional lstm
            max_len: amount of cnn layers
        """
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0).transpose(0, 1)
        self.register_buffer('pe', pe)

    def forward(self, x: Tensor) -> Tensor:
        """ Forwarding logic """

        x = x + self.pe[:x.size(0), :]
        return self.dropout(x)


class CNNTrans(ModelBase):

    def __init__(self, init_n_channels: int, out_channels: int, cnn_layers: int, kernel_size: tuple, padding: tuple, n_head: int, dropout: float, encoder_layers: int, embedding_pretrained: str, **kwargs):
        """ Constructor
        Args:
            init_n_channels: size of the incoming feature vector
            out_channels: amount of hidden neurons in the bidirectional lstm
            cnn_layers: amount of cnn layers
            kernel_size: kernel sizes of the cnn layers
            padding: padding of the cnn layers
            n_head: amount of attention heads
            dropout: amount of dropout
            encoder_layers: amount of encoder layers
            embedding_pretrained: path to language model weights
        """
        super().__init__()

        self.embedding = ESM1bEmbedding(embedding_pretrained, **kwargs)

        # CNN blocks
        self.conv = nn.ModuleList()
        for i in range(cnn_layers):
            self.conv.append(nn.Sequential(*[
                nn.Dropout(p=dropout),
                nn.Conv1d(in_channels=init_n_channels, out_channels=out_channels, kernel_size=kernel_size[i], padding=padding[i]),
                nn.ReLU(),
            ]))

        self.batch_norm = nn.BatchNorm1d(init_n_channels+(out_channels*2))

        # Transformer block
        self.pos_enc = PositionalEncoding(init_n_channels+(out_channels*2), dropout=dropout)
        self.encoder_layer = nn.TransformerEncoderLayer(d_model=init_n_channels+(out_channels*2), nhead=n_head, dropout=dropout)
        self.transformer_encoder = nn.TransformerEncoder(self.encoder_layer, num_layers=encoder_layers)

        # Task block
        self.ss8 = nn.Sequential(*[
            nn.Linear(in_features=init_n_channels+(out_channels*2), out_features=8),
        ])
        self.dis = nn.Sequential(*[
            nn.Linear(in_features=init_n_channels+(out_channels*2), out_features=1),
        ])
        self.rsa = nn.Sequential(*[
            nn.Linear(in_features=init_n_channels+(out_channels*2), out_features=1),
        ])
        self.phi = nn.Sequential(*[
            nn.Linear(in_features=init_n_channels+(out_channels*2), out_features=2),
            nn.Tanh()
        ])
        self.psi = nn.Sequential(*[
            nn.Linear(in_features=init_n_channels+(out_channels*2), out_features=2),
            nn.Tanh()
        ])

    def forward(self, x: Tensor, seq_lengths: Tensor) -> Dict[str, Tensor]:
        """Forwarding logic"""

        x = self.embedding(x, seq_lengths)

        x = x.permute(0, 2, 1)

        # concatenate channels from residuals and input + batch norm
        r = x
        for layer in self.conv:
            r = torch.cat([r, layer(x)], dim=1)

        x = self.batch_norm(r)

        # transformer encoder layers
        x = x.permute(0, 2, 1)

        x = self.pos_enc(x)
        x = self.transformer_encoder(x)

        # hidden neurons to classes
        ss8 = self.ss8(x)
        dis = self.dis(x)
        rsa = self.rsa(x)
        phi = self.phi(x)
        psi = self.psi(x)

        return {'ss8': ss8, 'dis': dis, 'rsa': rsa, 'phi': phi, 'psi': psi}
