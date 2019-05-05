import torch
import torch.nn as nn


class EncoderBlock(nn.Sequential):
    def __init__(self, in_channels, out_channels):
        super().__init__(
            nn.ReflectionPad2d(2),
            nn.Conv2d(
                in_channels=in_channels, out_channels=out_channels,
                kernel_size=5, stride=2, bias=False),
            nn.BatchNorm2d(num_features=out_channels),
            nn.ReLU(),
        )


class DecoderBlock(nn.Sequential):
    def __init__(self, in_channels, out_channels):
        super().__init__(
            nn.ConvTranspose2d(
                in_channels=in_channels, out_channels=out_channels,
                kernel_size=5, padding=2, stride=2, bias=False),
            nn.InstanceNorm2d(out_channels),
            nn.LeakyReLU(),
        )


class Encoder(nn.Module):
    def __init__(self, feat_size, num_latent, channels=[3, 64, 128, 256]):
        super().__init__()
        self.num_latent = num_latent
        self.feat_size = feat_size
        self.channels = channels
        self.convs = nn.Sequential(
            *[EncoderBlock(*channels[i:i+2]) for i in range(len(channels)-1)]
        )
        n_features = feat_size[0] * feat_size[1] * channels[-1]
        self.map = nn.Sequential(
            nn.Linear(n_features, num_latent, bias=False),
            nn.BatchNorm1d(num_features=num_latent),
        )

    def forward(self, x):
        x = self.convs(x)
        z = self.map(x.view(x.size()[0], -1))
        return z


class Decoder(nn.Module):
    def __init__(self, feat_size, num_latent, channels=[256, 256, 128, 64]):
        super().__init__()
        self.num_latent = num_latent
        self.feat_size = feat_size
        self.channels = channels
        n_features = feat_size[0] * feat_size[1] * channels[0]
        self.map = nn.Linear(num_latent, n_features)
        convs = [
            DecoderBlock(*channels[i:i+2]) for i in range(len(channels)-1)
        ] + [
            nn.ReflectionPad2d(2),
            nn.Conv2d(
                in_channels=channels[-1], out_channels=3,
                kernel_size=5, stride=1,
            )
        ]
        self.convs = nn.Sequential(*convs)

    def forward(self, x):
        x = self.map(x)
        h, w = self.feat_size
        x = x.view(x.size()[0], self.channels[0], h, w)
        return torch.tanh(self.convs(x))


class AE(nn.Module):
    def __init__(self, encoder, decoder):
        super().__init__()
        self.encoder = encoder
        self.decoder = decoder

    def forward(self, orig):
        z = self.encoder(orig)
        recon = self.decoder(z)
        return recon, z


class Discriminator(nn.Module):
    def __init__(self, feat_size):
        super().__init__()
        self.feat_size = feat_size
        self.convs = nn.Sequential(
            nn.ReflectionPad2d(2),
            nn.Conv2d(3, 32, kernel_size=5),
            nn.LeakyReLU(),
            #################
            nn.ReflectionPad2d(2),
            nn.Conv2d(32, 128, kernel_size=5, stride=2),
            nn.LeakyReLU(),
            #################
            nn.ReflectionPad2d(2),
            nn.Conv2d(128, 256, kernel_size=5, stride=2),
            nn.LeakyReLU(),
            #################
            nn.ReflectionPad2d(2),
            nn.Conv2d(256, 256, kernel_size=5, stride=2),
            nn.LeakyReLU(),
            #################
        )
        n_feat = self.feat_size[0] * self.feat_size[1] * 256
        self.fc = nn.Sequential(
            nn.Linear(in_features=n_feat, out_features=512),
            nn.LeakyReLU(),
            nn.Linear(in_features=512, out_features=1),
            nn.Sigmoid()
        )

    def forward(self, x):
        x = self.convs(x)
        x_feats = x
        x = x.view(len(x), -1)
        x = self.fc(x)
        return x, x_feats


class AeGan(nn.Module):
    def __init__(self, ae, discriminator):
        super().__init__()
        self.ae = ae
        self.discriminator = discriminator

    def forward(self, orig):
        raise NotImplementedError('Use `model.ae` or `model.discrinimator`.')


def get_model(feat_size=(9, 16), n_latent=1024):
    encoder = Encoder(feat_size, n_latent)
    decoder = Decoder(feat_size, n_latent)
    discriminator = Discriminator(feat_size)
    model = AeGan(AE(encoder, decoder), discriminator)
    return model