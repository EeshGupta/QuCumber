import numpy as np
import matplotlib.pyplot as plt
import torch

from qucumber.nn_states import PositiveWavefunction
from qucumber.callbacks import MetricEvaluator
from qucumber.callbacks import Timer

import qucumber.utils.training_statistics as ts
import qucumber.utils.data as data



listOptimizers = [
    "Adadelta",
    "Adam",
    "Adamax",
    "RMSprop",
    "SGD",
    "SGD $\gamma$ = 0.9",
    "NAG $\gamma$ = 0.9"
]

def trainRBM(numQubits,epochs,pbs,nbs,lr,k,numSamples,optimizer,**kwargs):
    '''
    Takes amplitudes and samples file as input and runs an RBM in order
    to reconstruct the quantum state. Returns a dictionary containing
    the fidelities and runtimes corresponding to certain epochs.

    :param numQubits: Number of qubits in the quantum state.
    :type numQubits: int
    :param epochs: Total number of epochs to train.
    :type epochs: int
    :param pbs: Positive batch size.
    :type pbs: int
    :param nbs: Negative batch size.
    :type nbs: int
    :param lr: Learning rate.
    :type lr: float
    :param k: Number of contrastive divergence steps in training.
    :type k: int
    :param numSamples: Number of samples to use from sample file. Can use "All"
    :type numSamples: int
    :param optimizer: The constructor of a torch optimizer.
    :type optimizer: torch.optim.Optimizer
    :param kwargs: Keyword arguments to pass to the optimizer

    :returns: Dictionary of fidelities and runtimes at various epochs.
    :rtype: dict["epochs"]
            dict["fidelities"]
            dict["times"]
    '''

    # Load the data corresponding to the amplitudes and samples
    # of the quantum system
    psi_path = r"Samples\{0}Q\AmplitudesP.txt".format(numQubits)
    train_path = r"Samples\{0}Q\Samples.txt".format(numQubits)
    train_data, true_psi = data.load_data(train_path, psi_path,
                                          numSamples=numSamples)

    # Specify the number of visible and hidden units and
    # initialize the RBM
    nv = train_data.shape[-1]
    nh = nv
    nn_state = PositiveWavefunction(num_visible = nv,num_hidden = nh,
                                    gpu = False)

    log_every = 100
    space = nn_state.generate_hilbert_space(nv)

    # And now the training can begin!
    callbacks = [
        MetricEvaluator(
            log_every,
            {"Fidelity": ts.fidelity, "KL": ts.KL},
            target_psi=true_psi,
            verbose=True,
            space=space
        ),
        Timer(verbose = True)
    ]

    nn_state.fit(
        train_data,
        epochs=epochs,
        pos_batch_size=pbs,
        neg_batch_size=nbs,
        lr=lr,
        k=k,
        callbacks=callbacks,
        optimizer=optimizer,
        **kwargs
    )

    results = {"epochs": np.arange(log_every, epochs + 1, log_every),
               "fidelities": callbacks[0].Fidelity,
               "times": callbacks[1].epochTimes}

    return results

def produceData(epochs,pbs,nbs,k,numQubits,numSamples):
    '''
    Writes a datafile containing lists of fidelities and runtimes for
    several epochs for various optimizers.

    :param epochs: Total number of epochs to train.
    :type epochs: int
    :param pbs: Positive batch size.
    :type pbs: int
    :param nbs: Negative batch size.
    :type nbs: int
    :param k: Number of contrastive divergence steps in training.
    :type k: int
    :param numQubits: Number of qubits in the quantum state.
    :type numQubits: int
    :param numSamples: Number of samples to use from sample file.
    :type numSamples: int

    :returns: None
    '''

    results = []
    results.append(trainRBM(numQubits,epochs,pbs,nbs,1,k,numSamples,torch.optim.Adadelta))
    results.append(trainRBM(numQubits,epochs,pbs,nbs,0.001,k,numSamples,torch.optim.Adam))
    results.append(trainRBM(numQubits,epochs,pbs,nbs,0.002,k,numSamples,torch.optim.Adamax))
    results.append(trainRBM(numQubits,epochs,pbs,nbs,0.01,k,numSamples,torch.optim.RMSprop))
    results.append(trainRBM(numQubits,epochs,pbs,nbs,0.01,k,numSamples,torch.optim.SGD))
    results.append(trainRBM(numQubits,epochs,pbs,nbs,0.01,k,numSamples,torch.optim.SGD,momentum=0.9))
    results.append(trainRBM(numQubits,epochs,pbs,nbs,0.01,k,numSamples,torch.optim.SGD,momentum=0.9,nesterov=True))

    datafile = open("TrainingCycles.txt","w")
    datafile.write("Batch size is {0}\n".format(pbs))
    datafile.write("\n")
    counter = 0
    for result in results:
        datafile.write("Optimizer is " + str(listOptimizers[counter]) + "\n")
        datafile.write("Epoch & Fidelity & Runtime" + " \n")
        for i in range(len(result["epochs"])):
            datafile.write(str(result["epochs"][i]) + " " +
                           str(round(result["fidelities"][i].item(),6)) + " " +
                           str(round(result["times"][i],6)) + "\n")
        datafile.write("\n")
        counter += 1
    datafile.close()

def graphData(filename):
    '''
    Graphs a plot of fidelity vs runtime

    :param filename: Name of file containing data
    :type filename: str

    :returns: None
    '''

    f = open(filename)
    lines = []
    line = f.readline()
    line = line.strip("\n")
    line = line.split(" ")
    pbs = line[3]
    line = f.readline()
    line = f.readline()
    fidelities = []
    runtimes = []

    counter = 0
    while line != "":
        if line == "\n":
            plt.plot(runtimes,fidelities,"-o",label = listOptimizers[counter])
            counter += 1
            fidelities = []
            runtimes = []
        elif line[0] == "E" or line[0] == "O":
            line = f.readline()
            continue
        else:
            line = line.strip("\n")
            line = line.split(" ")
            fidelities.append(float(line[1]))
            runtimes.append(float(line[2]))
        line = f.readline()

    plt.xlabel("Runtime (Seconds)")
    plt.ylabel("Fidelity")
    plt.title("Learning Curve for Various Optimizers with " +
              r"B = {0}".format(pbs))
    plt.legend()
    plt.savefig("LearningCurve",dpi = 200)
    f.close()

produceData(1000,100,100,1,15,"All")
graphData("TrainingCycles.txt")
