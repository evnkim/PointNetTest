import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable


class STNKd(nn.Module):
    # T-Net a.k.a. Spatial Transformer Network
    def __init__(self, k: int):
        super().__init__()
        self.k = k
        self.conv1 = nn.Sequential(nn.Conv1d(k, 64, 1), nn.BatchNorm1d(64))
        self.conv2 = nn.Sequential(nn.Conv1d(64, 128, 1), nn.BatchNorm1d(128))
        self.conv3 = nn.Sequential(nn.Conv1d(128, 1024, 1), nn.BatchNorm1d(1024))

        self.fc = nn.Sequential(
            nn.Linear(1024, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Linear(256, k * k),
        )

    def forward(self, x):
        """
        Input: [B,k,N]
        Output: [B,k,k]
        """
        B = x.shape[0]
        device = x.device
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = torch.max(x, 2)[0]

        x = self.fc(x)
        
        # Followed the original implementation to initialize a matrix as I.
        identity = (
            Variable(torch.eye(self.k, dtype=torch.float))
            .reshape(1, self.k * self.k)
            .expand(B, -1)
            .to(device)
        )
        x = x + identity
        x = x.reshape(-1, self.k, self.k)
        return x


class PointNetFeat(nn.Module):
    """
    Corresponds to the part that extracts max-pooled features.
    """
    def __init__(
        self,
        input_transform: bool = False,
        feature_transform: bool = False,
    ):
        super().__init__()
        self.input_transform = input_transform
        self.feature_transform = feature_transform

        if self.input_transform:
            self.stn3 = STNKd(k=3)
        if self.feature_transform:
            self.stn64 = STNKd(k=64)

        # point-wise mlp
        # TODO : Implement point-wise mlp model based on PointNet Architecture.
        self.pw_mlp = nn.Sequential(
                nn.Linear(3, 64),
                nn.BatchNorm1d(64),
                nn.ReLU(),
                nn.Linear(64, 64),
                nn.BatchNorm1d(64),
                nn.ReLU(),
        )
        
        self.pw_mlp2 = nn.Sequential(
            nn.Linear(64, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Linear(64, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Linear(128, 1024),
            nn.BatchNorm1d(1024),
            nn.ReLU(),
        )
        
        # self.max_pool = nn.MaxPool1d(1024)

    def forward(self, pointcloud):
        """
        Input:
            - pointcloud: [B,N,3]
        Output:
            - Global feature: [B,1024]
            - ...
        """

        # TODO : Implement forward function.
        print(pointcloud.shape)
        if(self.input_transform):
            transform = self.stn3(pointcloud.transpose(1,2))
            pointcloud = torch.matmul(pointcloud, transform)

        print(pointcloud.shape)
        
        B, N, _ = pointcloud.shape
        pointcloud = pointcloud.reshape((B * N, 3))  # Reshape to apply MLP to each point
        pointcloud = self.pw_mlp(pointcloud)
        features = pointcloud.reshape((B, N, 64)) # Reshape back
        
        # Another transformation
        if(self.feature_transform):
            transform = self.stn64(features.transpose(1,2))
            features = torch.matmul(features, transform)
        
        # Apply another point-wise MLP
        features = features.reshape((B * N, 64))
        features = self.pw_mlp2(features)
        features = features.reshape((B, N, 1024))
        
        out, _ = torch.max(features, dim=1)

        print(out.shape)
        
        return out


class PointNetCls(nn.Module):
    def __init__(self, num_classes, input_transform, feature_transform):
        super().__init__()
        self.num_classes = num_classes
        
        # extracts max-pooled features
        self.pointnet_feat = PointNetFeat(input_transform, feature_transform)
        
        # returns the final logits from the max-pooled features.
        # TODO : Implement MLP that takes global feature as an input and return logits.
        self.classify = nn.Sequential(
            nn.Linear(1024, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(p=0.5),
            nn.Linear(256, num_classes),
        )

    def forward(self, pointcloud):
        """
        Input:
            - pointcloud [B,N,3]
        Output:
            - logits [B,num_classes]
            - ...
        """
        # TODO : Implement forward function.
        x = self.pointnet_feat(pointcloud)
        logits = self.classify(x)
        
        return logits


class PointNetPartSeg(nn.Module):
    def __init__(self, m=50):
        super().__init__()

        # returns the logits for m part labels each point (m = # of parts = 50).
        # TODO: Implement part segmentation model based on PointNet Architecture.
        self.stn3 = STNKd(k=3)
        self.stn64 = STNKd(k=64)

        self.pw_mlp = nn.Sequential(
                nn.Linear(3, 64),
                nn.BatchNorm1d(64),
                nn.ReLU(),
                nn.Linear(64, 64),
                nn.BatchNorm1d(64),
                nn.ReLU(),
        )
        
        self.pw_mlp2 = nn.Sequential(
            nn.Linear(64, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Linear(64, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Linear(128, 1024),
            nn.BatchNorm1d(1024),
            nn.ReLU(),
        )
        
        self.seg_mlp = nn.Sequential(
            nn.Linear(1088, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Linear(128, m),
        )
        
        

    def forward(self, pointcloud):
        """
        Input:
            - pointcloud: [B,N,3]
        Output:
            - logits: [B,50,N] | 50: # of point labels
            - ...
        """
        # TODO: Implement forward function.
        transform = self.stn3(pointcloud.transpose(1,2))
        pointcloud = torch.matmul(pointcloud, transform)
        
        B, N, _ = pointcloud.shape
        pointcloud = pointcloud.reshape((B * N, -1))  # Reshape to apply MLP to each point
        pointcloud = self.pw_mlp(pointcloud)
        features = pointcloud.reshape((B, N, -1))  # Reshape back
        
        # Another transformation
        transform = self.stn64(features.transpose(1,2))
        features = torch.matmul(features, transform)
        
        # Apply another point-wise MLP
        features2 = features.reshape((B * N, -1))
        features2 = self.pw_mlp2(features2)
        features2 = features2.reshape((B, N, -1))
        
        global_feature, _ = torch.max(features2, dim=1)
        
        print(features.shape)
        print(global_feature.shape)
        
        concat_feature = torch.cat((features, global_feature.unsqueeze(1).repeat(1, N, 1)), dim=2)
        
        concat_feature = concat_feature.reshape((B * N, -1))
        concat_feature = self.seg_mlp(concat_feature)
        logits = concat_feature.reshape((B,N,-1))
        logits = logits.permute(0, 2, 1)
        
        return logits
        
        


class PointNetAutoEncoder(nn.Module):
    def __init__(self, num_points):
        super().__init__()
        self.pointnet_feat = PointNetFeat()

        # Decoder is just a simple MLP that outputs N x 3 (x,y,z) coordinates.
        # TODO : Implement decoder.
        self.decoder = nn.Sequential(
            nn.Linear(1024, num_points / 4),
            nn.BatchNorm1d(num_points / 4),
            nn.ReLU(),
            nn.Linear(num_points / 4, num_points / 2),
            nn.BatchNorm1d(num_points / 2),
            nn.ReLU(),
            nn.Linear(num_points / 2, num_points),
            nn.Dropout(p=0.5),
            nn.BatchNorm1d(num_points),
            nn.ReLU(),
            nn.Linear(num_points, num_points * 3),
        )
        

    def forward(self, pointcloud):
        """
        Input:
            - pointcloud [B,N,3]
        Output:
            - pointcloud [B,N,3]
            - ...
        """
        # TODO : Implement forward function.
        encoding = self.pointnet_feat(pointcloud)
        decode = self.decoder(encoding)
        decode = decode.reshape(-1, pointcloud.shape[1], 3)
        return decode


def get_orthogonal_loss(feat_trans, reg_weight=1e-3):
    """
    a regularization loss that enforces a transformation matrix to be a rotation matrix.
    Property of rotation matrix A: A*A^T = I
    """
    if feat_trans is None:
        return 0

    B, K = feat_trans.shape[:2]
    device = feat_trans.device

    identity = torch.eye(K).to(device)[None].expand(B, -1, -1)
    mat_square = torch.bmm(feat_trans, feat_trans.transpose(1, 2))

    mat_diff = (identity - mat_square).reshape(B, -1)

    return reg_weight * mat_diff.norm(dim=1).mean()
