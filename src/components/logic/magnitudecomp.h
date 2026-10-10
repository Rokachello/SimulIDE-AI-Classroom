/***************************************************************************
 *   Copyright (C) 2024 by Santiago González                               *
 *                                                                         *
 ***( see copyright.txt file at root folder )*******************************/

#pragma once

#include "iocomponent.h"
#include "e-element.h"

class LibraryItem;

class MagnitudeComp : public IoComponent, public eElement
{
    public:
        MagnitudeComp( QString type, QString id );
        ~MagnitudeComp();

 static Component* construct( QString type, QString id );
 static LibraryItem* libraryItem();

        void stamp() override;
        void voltChanged() override;
        void runEvent() override { IoComponent::runOutputs(); }

        int bits() { return m_bits; }
        void setBits( int b );

    private:

        int m_bits;
};
