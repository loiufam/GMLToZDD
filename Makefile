CC	= g++

DIR	= .
INCL    = -I$(DIR)/TdZdd/include -I$(DIR)/MyTdZdd/

PRG     = main
PRG64   = main64
PRGGML  = gml_to_matrix

OPT 	= -std=c++17 -O3 $(INCL)
OPT64   = $(OPT) -DB_64
OPTGML = -std=c++17


OBJ	= main.o
OBJ64   = main_64.o
OBJGML = gml_to_matrix.o

all:	$(PRG)    

64:	$(PRG64)   

gml: $(PRGGML)
	

$(PRG): $(OBJ)
	$(CC) $(OPT) $(OBJ) -o $(PRG)

$(PRG64): $(OBJ64)
	$(CC) $(OPT64) $(OBJ64) -o $(PRG64)

$(PRGGML): $(OBJGML)
	$(CC) $(OPTGML) $(OBJGML) -o $(PRGGML)

main.o: main.cpp
	$(CC) $(OPT) -c main.cpp

main_64.o: main.cpp
	$(CC) $(OPT64) -c main.cpp -o main_64.o

gml_to_matrix.o: gml_to_matrix.cpp
	$(CC) $(OPTGML) -c gml_to_matrix.cpp

clean:
	rm -f $(OBJ) $(OBJ64) $(OBJGML)



