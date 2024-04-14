import torch
import torch.nn as nn
import typing
from dataclasses import dataclass


class AbsPosEmbedding(nn.Module):
    def __init__(self, token_size: int, max_len: int, d_model: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.token_embedding = nn.Embedding(token_size, d_model, padding_idx=0)
        self.pos_embedding = nn.Embedding(max_len + 1, d_model, padding_idx=0)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        xlen = x.size(-1)
        mask = (x > 0).long()
        position = torch.arange(1, xlen+1).to(x.device)
        position = position * mask
        x = self.token_embedding(x)
        x += self.pos_embedding(position)
        return self.dropout(x)


@dataclass
class AbsPosEncoderDecoderConfig:
    token_size: int
    max_len: int = 512
    d_model: int = 768
    nhead: int = 8
    num_encoder_layers: int = 6
    num_decoder_layers: int = 6
    dropout: float = 0.1


class AbsPosEncoderDecoder(nn.Module):
    def __init__(self, conf: AbsPosEncoderDecoderConfig) -> None:
        super().__init__()
        self.conf = conf
        self.embedding = AbsPosEmbedding(
            conf.token_size, conf.max_len, conf.d_model, conf.dropout)
        self.transformer = nn.Transformer(
            conf.d_model, conf.nhead, conf.num_encoder_layers, conf.num_decoder_layers, dropout=conf.dropout, activation='gelu', batch_first=True)
        self.token_output = nn.Linear(
            conf.d_model, conf.token_size, bias=False)

    def load_ckpt(self, ckpt_files: typing.List[str]) -> None:
        self.load_state_dict(torch.load(
            ckpt_files[0], map_location=torch.device('cpu')))

    def forward_(self, src: torch.Tensor, tgt: torch.Tensor) -> torch.Tensor:
        mask = nn.Transformer.generate_square_subsequent_mask(
            tgt.size(-1), device=tgt.device)
        src = self.embedding(src)
        tgt = self.embedding(tgt)
        return self.transformer(src, tgt, tgt_mask=mask, tgt_is_causal=True)

    def forward_feature(self, src: torch.Tensor, tgt: torch.Tensor) -> torch.Tensor:
        out = self.forward_(src, tgt)
        indices = (tgt > 0).sum(dim=-1, keepdim=True) - 1
        indices = indices.unsqueeze(-1).repeat(*
                                               [1 for _ in range(tgt.dim())], out.shape[-1])
        return torch.gather(input=out, dim=-2, index=indices).squeeze()

    def forward_generation(self, src: torch.Tensor, tgt: torch.Tensor) -> torch.Tensor:
        out = self.forward_(src, tgt)
        return self.token_output(out)


@dataclass
class AbsPosEncoderCausalConfig:
    token_size: int
    max_len: int = 256
    d_model: int = 768
    nhead: int = 8
    num_layers: int = 12
    dropout: float = 0.1


class AbsPosEncoderCausal(nn.Module):
    def __init__(self, conf: AbsPosEncoderCausalConfig) -> None:
        super().__init__()
        self.conf = conf
        self.embedding = AbsPosEmbedding(
            conf.token_size, conf.max_len, conf.d_model, conf.dropout)
        layer = nn.TransformerEncoderLayer(
            conf.d_model, conf.nhead, dropout=conf.dropout, batch_first=True, activation='gelu')
        self.transformer = nn.TransformerEncoder(
            layer, conf.num_layers, norm=nn.LayerNorm(conf.d_model))
        self.token_output = nn.Linear(
            conf.d_model, conf.token_size, bias=False)

    def load_ckpt(self, ckpt_files: typing.List[str]) -> None:
        self.load_state_dict(torch.load(
            ckpt_files[0], map_location=torch.device('cpu')))

    def forward_(self, x: torch.Tensor) -> torch.Tensor:
        mask = nn.Transformer.generate_square_subsequent_mask(
            x.size(-1), device=x.device)
        x = self.embedding(x)
        return self.transformer(x, mask=mask, is_causal=True)

    def forward_feature(self, x: torch.Tensor) -> torch.Tensor:
        out = self.forward_(x)
        indices = (x > 0).sum(dim=-1, keepdim=True) - 1
        indices = indices.unsqueeze(-1).repeat(*
                                               [1 for _ in range(x.dim())], out.shape[-1])
        return torch.gather(input=out, dim=-2, index=indices).squeeze()

    def forward_generation(self, x: torch.Tensor) -> torch.Tensor:
        out = self.forward_(x)
        return self.token_output(out)
