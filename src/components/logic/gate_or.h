/***************************************************************************
 *   Copyright (C) 2012 by Santiago González                               *
 *                                                                         *
 ***( see copyright.txt file at root folder )*******************************/

#pragma once

#include "gate.h"
#include "component.h"

class LibraryItem;

class OrGate : public Gate
{
    public:
        OrGate( QString type, QString id );
        ~OrGate();

 static Component* construct( QString type, QString id );
 static LibraryItem* libraryItem();

    protected:
        bool calcOutput( int inputs ) override;
        void updatePath() override;
};
