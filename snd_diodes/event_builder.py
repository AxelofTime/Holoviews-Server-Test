import numpy as np
import pandas as pd
from collections import deque

def basic_event_builder(*args,**kwargs):
    #Stolen from Nolan
    """
    Pass any number of pandas Series and return an event built pandas
    DataFrame.  Kwargs can be used to name the columns of the returned
    DataFrame.
    """
    data_table = dict()
    [data_table.setdefault(col,args[col]) for col in range(len(args))]
    [data_table.setdefault(col,kwargs[col]) for col in kwargs]
    full_frame = pd.DataFrame(data_table)
    return full_frame.dropna()
