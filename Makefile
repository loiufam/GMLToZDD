CC	= g++

DIR	= .
INCL    = -I$(DIR)/TdZdd/include -I$(DIR)/MyTdZdd/

PRG     = main
PRG64   = main64

OPT 	= -std=c++17 -O3 -fopenmp $(INCL)
OPT64   = $(OPT) -DB_64


OBJ	= main.o
OBJ64   = main_64.o

all:	$(PRG)    

64:	$(PRG64)   

	

$(PRG): $(OBJ)
	$(CC) $(OPT) $(OBJ) -o $(PRG)

$(PRG64): $(OBJ64)
	$(CC) $(OPT64) $(OBJ64) -o $(PRG64)


main.o: main.cpp
	$(CC) $(OPT) -c main.cpp

main_64.o: main.cpp
	$(CC) $(OPT64) -c main.cpp -o main_64.o


clean:
	rm -f $(OBJ) $(OBJ64) $(OBJGML)



