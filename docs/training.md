# Training and fine-tuning

## The public model (`train.sh`)

Stock YOLO11 has no bee class (COCO has no insects that small), so a fresh install
counts ~0 until a bee model exists. `counter/train.sh` reproduces the reference model:

| | |
|---|---|
| dataset | Roboflow Universe `thesisbees / bee-detector-6zlc9`, version 4, ~8,175 annotated images (16.6k train / 1.6k val after augmentation) |
| base | `yolo11n.pt` |
| settings | imgsz 640, epochs 40, batch 16, patience 10 |
| result | mAP50 **0.944**, precision 0.92, recall 0.91 |
| time | ~3–4 h on an RTX 4070 SUPER with the GPU otherwise idle |

You need a free Roboflow account and its API key (Settings → API Keys). Keys are
account-level, so any key works for any public dataset. The script prompts for it
or reads `RF_API_KEY`; it is never stored in the repo.

Two things learned the hard way, both handled by the script:

- **Free the GPU first.** With two counters and a 30B Ollama model resident, a 12 GB
  card OOMs down to batch 4 and each epoch takes ~19 min instead of ~5. The script
  stops the counters and sends Ollama `keep_alive: 0` before training.
- **Run it in tmux.** A dropped SSH session sends Ctrl-C to training. Ultralytics
  saves `best.pt` every epoch, so an interrupted run is still usable — an epoch-2
  checkpoint already reached mAP50 0.847 — but let it finish.

Back the resulting `models/bees.pt` up off the box. It is ~5 MB and several hours of GPU time.

## Your own hives (`finetune.sh`)

The public set was shot on other people's hives. Your angle, board colour and light
differ, and fine-tuning on a few hundred of your own frames is the biggest accuracy
upgrade available. The loop:

1. On the Pi control center (`:8080`) turn **Auto-capture** on for a camera and leave
   the page open. One frame every 30 s. Do this across a few sessions — morning,
   afternoon, busy, quiet. Variety beats volume; 200–300 per camera is plenty.
2. On the GPU box: `PI=<pi-ip> /opt/beecounter/finetune.sh`. It downloads the frames,
   auto-labels them with the current `bees.pt`, writes preview images with boxes
   drawn, mixes them with the public set and fine-tunes from `bees.pt` for 15 epochs
   at a low learning rate.
3. **Look at `own-hives/labelled/preview/`** before trusting the result. Auto-labels
   inherit the model's mistakes. Frames where the boxes are wrong should be deleted
   from `own-hives/labelled/images` and `labels` (same basename) and the script re-run
   — or corrected in a labelling tool if you want the last few percent.

`bees-prev.pt` is always the previous model; swap it back if counts get worse.

This script is assembled from pieces that work individually but has had the least
field time of anything in the repo. Reports welcome.
