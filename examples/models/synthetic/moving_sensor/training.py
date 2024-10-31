import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import torch.optim as optim
import torch
import torch.nn as nn
import numpy as np
from dataset import read_data, generate_batches, PointNeighborhood
#from model3 import SpatialRegressor3
from model4 import MultiHeadSpatialRegressor

def monitor_training(H, parameters):
    plt.style.use("ggplot")
    plt.figure()
    plt.plot(np.arange(0, len(H["train_loss"])), H["train_loss"], label="train_loss")
    plt.plot(np.arange(0, len(H["val_loss"])), H["val_loss"], label="val_loss")
    plt.title("Training/Val Losses")
    plt.xlabel("Epoch #")
    plt.ylabel("Loss")
    plt.legend()
    plt.savefig(parameters["plot"])
    plt.close()

def plot_debugging(tanh_out):

    plt.figure()
    legends = []
    for i, t in enumerate(tanh_out): # exclude output layer
        print(t.shape)
        print('layer %d: mean %+.2f, std %.2f, saturated: %.2f%%' % (i, t.mean(), t.std(), (t.abs() > 0.97).float().mean()*100))
        #print('layer %d: mean %+.2f, std %.2f, saturated: %.2f%%' % (i, t.mean(), t.std(), (t.abs() <= 1e-5).float().mean()*100))
        hy, hx = torch.histogram(t, density=True)
        print(hy.shape)
        print(hx.shape)
        plt.plot(hx[:-1].detach(), hy.detach())
        legends.append(f'layer {i}')
    plt.legend(legends)
    plt.title('activation distribution')
    plt.show()

    plt.figure()
    legends = []
    for i, layer in enumerate(tanh_out):
            t = layer.grad
            print('layer %d: mean %+f, std %e' % (i, t.mean(), t.std()))
            hy, hx = torch.histogram(t, density=True)
            print(hy.shape)
            print(hx.shape)
            plt.plot(hx[:-1].detach(), hy.detach())
            legends.append(f'layer {i}')
    plt.legend(legends)
    plt.title('activation distribution')
    plt.show()

    plt.figure()
    legends = []
    for i, p in enumerate(model.parameters()):
        if p.ndim == 2: # restricting to the weights of the linear layers
            plt.plot([ud[j][i] for j in range(len(ud))])
            legends.append('param %d' % i)

    # these ratios should be around 1e-3
    plt.plot([0, len(ud)], [-3, -3], 'k')
    plt.legend(legends)
    plt.show()

parameters = {
    "batch_size": None,
    "normalize_timescale": 2*np.pi,
    "learning_rate": 0.5,
    "weight_decay": 1e-4,
    "momentum": 0.9,
    "random_noise": False,
    "noise_scale": None,
    "hidden_size": 128, #96,
    "dropout": 0.5,
    "num_epochs": 2500,
    "device": "cpu",
    "last_model": "saved_models/model_6.pt",
    "best_model": "saved_models/best_model_6.pt",
    "plot": "plots/training_6.png",
    "save_every": 100,
    "log_every": 100,
    "n_heads": 4
}

train_state = {
    "train_loss": [],
    "val_loss": [],
    "best_loss": 9999.9
}

if torch.cuda.is_available():
    parameters["device"] = "cuda"

print(parameters)

train_data = read_data("../flight_train.csv")
val_data = read_data("../flight_val.csv")

train_dataset = PointNeighborhood(train_data, 
                                  train=True, 
                                  normalize_time_difference=parameters["normalize_timescale"], # training the model to predict looking back at this interval
                                  hidden=parameters["hidden_size"]//parameters["n_heads"],
                                  random_noise=parameters["random_noise"], 
                                  noise_scale=parameters["noise_scale"])


val_dataset = PointNeighborhood(val_data,
                                train=False,
                                hidden=parameters["hidden_size"]//parameters["n_heads"],
                                normalize_time_difference=parameters["normalize_timescale"]) # training the model to predict looking back at this interval

#model = SpatialRegressor3(hidden=parameters["hidden_size"], prob=parameters["dropout"])
model = MultiHeadSpatialRegressor(hidden=parameters["hidden_size"], n_head=parameters["n_heads"], prob=parameters["dropout"])

num_params = sum(param.numel() for param in model.parameters())

print(f'n parameters: {num_params}')

model = model.to(parameters["device"])

loss_func = nn.MSELoss()
#loss_func = nn.L1Loss()
optimizer = optim.Adam(model.parameters(), lr=parameters["learning_rate"], weight_decay=parameters["weight_decay"])
#optimizer = optim.SGD(model.parameters(), lr=parameters["learning_rate"], momentum=parameters["momentum"], weight_decay=parameters["weight_decay"])

#decayRate = 0.995
#lr_scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer=optimizer, gamma=decayRate)

for name, param in model.named_parameters():
    if param.ndim == 2:
        param.data *= 5/3 #(2/(1 + 0.25 ** 2)) ** (1/2) # 2 ** (1/2) #5/3 # gain
    if name == "linear2_regression.weight":
        param.data *= 0.1 #1.0 #0.1
    if name == "linear2_regression.bias":
        param.data *= 0.0

ud = []

for epoch_index in range(parameters["num_epochs"]):

    train_batch_generator = generate_batches(train_dataset,
                                             batch_size=len(train_dataset),
                                             device=parameters["device"],
                                             drop_last=False)
    running_loss = 0.0

    model.train()

    if epoch_index < 550: # warmup
        lr = (1/(1+0.1*(700-epoch_index))) * 0.5
        optimizer.param_groups[0]['lr'] = lr
        lr_first_half = lr
    else:
        lr = (1/(1+0.1*(epoch_index-550))) * lr_first_half
        optimizer.param_groups[0]['lr'] = lr

    for batch_index, batch_dict in enumerate(train_batch_generator):

        optimizer.zero_grad()

        y_pred = model(
                u=batch_dict["x_data"].float(), 
                mask=batch_dict["mask"])

        loss = loss_func(y_pred, batch_dict["y_target"].float())


        loss_batch = loss.item()
        running_loss += (loss_batch - running_loss) / (batch_index + 1)

        #model.heads.heads[0].x_main.retain_grad()
        #model.heads.heads[0].x_main_1.retain_grad()
        #model.heads.heads[0].x_main_2.retain_grad()
        #model.heads.heads[0].x_attn.retain_grad()
        #model.heads.heads[0].x_attn_1.retain_grad()
        #model.ff.x0.retain_grad()
        #model.ff.x_1.retain_grad()
        #model.ff.x_2.retain_grad()

        loss.backward()


        #g['lr'] = 0.005

        #if epoch_index < 100:
        #    for g in optimizer.param_groups:
        #        g['lr'] = 0.005
        #elif epoch_index > 2000:
        #    for g in optimizer.param_groups:
        #        g['lr'] = 0.005
        #else:
        #    for g in optimizer.param_groups:
        #        g['lr'] = 0.01

        optimizer.step()

        #with torch.no_grad():
        #    # how grade are the updates to the values of the tensors
        #    ud.append([(parameters["learning_rate"]*p.grad.std() / p.data.std()).log().item() for p in model.parameters()])
        
        #if (epoch_index) == 500:
        #    #plot_debugging([model.x_main, model.x_main_1, model.x_main_2, 
        #    #                model.x_attn, model.x_attn_1, 
        #    #                model.x0, model.x_1, model.x_2])
        #    plot_debugging([model.heads.heads[0].x_main, model.heads.heads[0].x_main_1, model.heads.heads[0].x_main_2, 
        #                    model.heads.heads[0].x_attn, model.heads.heads[0].x_attn_1, 
        #                    model.ff.x0, model.ff.x_1, model.ff.x_2])
        #    print(loss)


    #if epoch_index > 5:
    train_loss = running_loss
    train_state["train_loss"].append(np.log10(running_loss))

    val_batch_generator = generate_batches(val_dataset,
                                           batch_size=len(val_dataset),
                                           device=parameters["device"],
                                           shuffle=False,
                                           drop_last=False)

    running_loss = 0.0

    model.eval()

    for batch_index, batch_dict in enumerate(val_batch_generator):
    
        y_pred = model(
                u=batch_dict["x_data"].float(), 
                mask=batch_dict["mask"])

        loss = loss_func(y_pred, batch_dict["y_target"].float())
        loss_batch = loss.item()
        running_loss += (loss_batch - running_loss) / (batch_index + 1)

    #if epoch_index > 5:
    train_state["val_loss"].append(np.log10(running_loss))


    #if epoch_index > 5:
    if (epoch_index+1) % parameters["log_every"] == 0:
        print(f"[INFO] epoch: {epoch_index}/{parameters['num_epochs']}, training loss: {train_loss}, validation loss: {running_loss}")
        print(f"[INFO] lr: {optimizer.param_groups[0]['lr']}")
        monitor_training(train_state, parameters)

    if (epoch_index+1) % parameters["save_every"] == 0:
        
        torch.save({
            'epoch': epoch_index,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'train_state': train_state,
            'parameters': parameters
        }, parameters["last_model"])

        print("[INFO] saving model checkpoint")

    if train_state["val_loss"][-1] < train_state["best_loss"]:
        
        torch.save({
            'epoch': epoch_index,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'train_state': train_state,
            'parameters': parameters
        }, parameters["best_model"])

        train_state["best_loss"] = train_state["val_loss"][-1]

        print(f"[INFO] saving best model checkpoint: {running_loss}")

torch.save({
    'epoch': -1,
    'model_state_dict': model.state_dict(),
    'optimizer_state_dict': optimizer.state_dict(),
    'train_state': train_state,
    'parameters': parameters
}, parameters["last_model"])

print("[INFO] saving model checkpoint")



