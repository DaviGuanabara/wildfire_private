import torch.nn as nn
import torch

class Head(nn.Module):
    def __init__(self, hidden=32, features=3, prob=0.5):
        super(Head, self).__init__()

        self.features = features
        self.hidden = hidden

        self.linear1_before_aggr = nn.Linear(self.features, hidden, bias=False)
        self.bn1 = nn.BatchNorm1d(num_features=hidden)
        self.activation1_before_aggr = nn.Tanh() #nn.PReLU() #LeakyReLU() #nn.Tanh() #nn.ReLU()
        self.dropout1_aggr = nn.Dropout(p=prob)

        self.linear12_before_aggr = nn.Linear(hidden, hidden, bias=False)
        self.bn12 = nn.BatchNorm1d(num_features=hidden)
        self.activation12_before_aggr = nn.Tanh() #nn.PReLU() #LeakyReLU() #nn.Tanh() #nn.ReLU()
        self.dropout12_aggr = nn.Dropout(p=prob)

        self.linear2_before_aggr = nn.Linear(hidden, hidden, bias=False)
        self.bn2 = nn.BatchNorm1d(num_features=hidden)
        self.activation2_before_aggr = nn.Tanh() #nn.PReLU() #LeakyReLU() #nn.Tanh()

        ##############

        self.linear1_attn = nn.Linear(self.features, hidden, bias=False)
        self.bn1_attn = nn.BatchNorm1d(num_features=hidden)
        self.activation1_attn = nn.Tanh() #nn.PReLU() #LeakyReLU() #nn.Tanh() #nn.ReLU()
        self.dropout1_attn = nn.Dropout(p=prob)

        self.linear12_attn = nn.Linear(hidden, hidden, bias=False)
        self.bn12_attn = nn.BatchNorm1d(num_features=hidden)
        self.activation12_attn = nn.Tanh() #nn.PReLU() #LeakyReLU() #nn.Tanh() #nn.ReLU()
        self.dropout12_attn = nn.Dropout(p=prob)

        self.linear2_attn = nn.Linear(hidden, hidden, bias=False)
        self.bn2_attn = nn.BatchNorm1d(num_features=hidden)

        self.softmax = nn.Softmax(dim=1) # softmax in the neighbors dim
        ################

    def forward(self, u, mask):

        # u: (batch, neighbors, features)
        # example: (2, 3, 4)

        # mask: (batch, neighbors, hidden)
        # example: (2, 3, 32)

        batch_size = u.shape[0]

        # (batch * neighbors, features)
        input = u.view(-1, self.features)
        
        # (batch * neighbors, hidden)

        x_main = self.linear1_before_aggr(input)
        x_main = self.bn1(x_main)
        self.x_main = self.activation1_before_aggr(x_main)

        x_main_1 = self.dropout1_aggr(self.x_main)
        x_main_1 = self.linear12_before_aggr(x_main_1)
        x_main_1 = self.x_main + x_main_1
        x_main_1 = self.bn12(x_main_1)
        self.x_main_1 = self.activation12_before_aggr(x_main_1)

        x_main_2 = self.dropout12_aggr(self.x_main_1)
        x_main_2 = self.linear2_before_aggr(x_main_2)
        x_main_2 = self.x_main_1 + x_main_2
        x_main_2 = self.bn2(x_main_2)
        self.x_main_2 = self.activation2_before_aggr(x_main_2)

        # (batch, neighbors, hidden)
        x_main_out = self.x_main_2.view(batch_size, -1, self.hidden)
   
        # attention leg
        # (batch * neighbors, features)
        x_attn = self.linear1_attn(input)
        x_attn = self.bn1_attn(x_attn)
        self.x_attn = self.activation1_attn(x_attn) #nn.ReLU()

        x_attn_1 = self.dropout1_attn(self.x_attn)
        x_attn_1 = self.linear12_attn(x_attn_1)
        x_attn_1 = self.x_attn + x_attn_1
        x_attn_1 = self.bn12_attn(x_attn_1)
        self.x_attn_1 = self.activation12_attn(x_attn_1) #nn.ReLU()

        # (batch * neighbors, hidden)
        x_attn_out = self.dropout12_attn(self.x_attn_1)
        x_attn_out = self.linear2_attn(x_attn_out)

        # (batch, neighbors, hidden)
        x_attn_out = x_attn_out.view(batch_size, -1, self.hidden)

        # (batch, neighbors, hidden)
        x_attn_out = x_attn_out.masked_fill(mask==0, -float("inf"))

        # (batch, neighbors, features)
        x_attn_out = self.softmax(x_attn_out) # softmax in the neighbors dim

        x = x_main_out * x_attn_out # element wise multiplication by the weights

        # (batch, features)
        x = x.sum(dim=1)

        return x

class MultiHead(nn.Module):
    def __init__(self, num_heads, head_size, features, prob):
        super().__init__()

        self.heads = nn.ModuleList([Head(head_size, features, prob) for _ in range(num_heads)])
        self.proj = nn.Linear(num_heads*head_size, num_heads*head_size)
        self.dropout = nn.Dropout(prob)

    def forward(self, x, mask):
        out = torch.cat([h(x, mask) for h in self.heads], dim=-1)
        out = self.dropout(self.proj(out))
        return out

class Feedforward(nn.Module):
    def __init__(self, hidden, prob):
        super().__init__()

        self.dropout1 = nn.Dropout(p=prob)
        self.linear1_after_aggr = nn.Linear(hidden, hidden, bias=False)
        self.bn3 = nn.BatchNorm1d(num_features=hidden)
        self.activation1_after_aggr = nn.Tanh() #nn.PReLU() #LeakyReLU() #nn.Tanh() #nn.ReLU()

        self.dropout12 = nn.Dropout(p=prob)
        self.linear12_after_aggr = nn.Linear(hidden, hidden, bias=False)
        self.bn12 = nn.BatchNorm1d(num_features=hidden)
        self.activation12_after_aggr = nn.Tanh() #nn.PReLU() #LeakyReLU() #nn.Tanh() #nn.ReLU()

        self.dropout2 = nn.Dropout(p=prob)
        self.linear2_after_aggr = nn.Linear(hidden, hidden, bias=False)
        self.bn4 = nn.BatchNorm1d(num_features=hidden)
        self.activation2_after_aggr = nn.Tanh() #nn.PReLU() #LeakyReLU() #nn.Tanh()

        self.bn5 = nn.BatchNorm1d(num_features=hidden)
        self.dropout3 = nn.Dropout(p=prob)
        self.linear2_regression = nn.Linear(hidden, 1)

    def forward(self, x):

        # ------- pass the aggregated node vetor in the MLP-phi, which is responsible for the regression
        #x = self.dropout1(x)

        # (batch, features)
        x0 = self.dropout1(x)
        x0 = self.linear1_after_aggr(x0)
        x0 = x + x0
        x0 = self.bn3(x0)
        self.x_0 = self.activation1_after_aggr(x0)
        

        x_1 = self.dropout12(self.x_0)
        x_1 = self.linear12_after_aggr(x_1)
        x_1 = x_1 + self.x_0
        x_1 = self.bn12(x_1)
        self.x_1 = self.activation12_after_aggr(x_1)


        x_2 = self.dropout2(self.x_1)
        x_2 = self.linear2_after_aggr(x_2)
        x_2 = x_2 + self.x_1
        x_2 = self.bn4(x_2)
        self.x_2 = self.activation2_after_aggr(x_2)

        x_out = self.dropout3(self.x_2)
        x_out = self.linear2_regression(x_out)

        return x_out


class MultiHeadSpatialRegressor(nn.Module):
    def __init__(self, hidden=32, features=4, prob=0.5, n_head=4):
        super(MultiHeadSpatialRegressor, self).__init__()

        head_size = hidden // n_head
        self.heads = MultiHead(num_heads=n_head, head_size=head_size, features=features, prob=prob) # 4 heads of 8-dim self attention
        self.ff = Feedforward(hidden=hidden, prob=prob)

    def forward(self, u, mask):
        x = self.heads(u, mask)
        x = self.ff(x)

        return x