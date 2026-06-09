# Installing required packages
```
pip install -r requirements.txt
```

# Running the cocotb tests
```
cd test
make
```
or if you also want waveform otuput
```
cd test
make WAVES=1
```

## To open waveforms in GTKwave
```
gtkwave --save tb.gtkw  sim_build/rtl/tb.fst
```
# Running Symbiyosys tests
```
cd sby  
sby -f config.sby
```