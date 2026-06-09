# Running the test
```
cd test
make
```
or if you also want waveform otuput
```
cd test
make WAVES=1
```

# To open waveforms in GTKwave
```
gtkwave --save tb.gtkw  sim_build/rtl/tb.fst
```
