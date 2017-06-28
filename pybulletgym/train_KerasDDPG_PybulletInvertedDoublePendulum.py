#!/usr/bin/env python

import Trainer
import datetime
import argparse
import pybulletgym.envs

trainer = Trainer.Trainer()

argparser = argparse.ArgumentParser()
Trainer.add_opts(argparser)

# precoded options
opts = argparser.parse_args()
opts.agent="KerasDDPGAgent-v0"
opts.env="PybulletInvertedDoublePendulum-v0"
opts.train_for=10000000
opts.test_for=0
datenow = '{:%Y%m%d%H%M%S}'.format(datetime.datetime.now())
opts.save_file="checkpoints/KerasDDPG-InvertedDoublePendulum-v0-"+datenow+".h5"

print("\n OPTS", opts)

trainer.setup_exercise(opts)


