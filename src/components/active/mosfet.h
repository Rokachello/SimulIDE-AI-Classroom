/***************************************************************************
 *   Copyright (C) 2016 by Santiago González                               *
 *                                                                         *
 ***( see copyright.txt file at root folder )*******************************/

#pragma once

#include "e-mosfet.h"
#include "component.h"

class LibraryItem;

class Mosfet : public Component, public eMosfet
{
    public:
        Mosfet( QString type, QString id );
        ~Mosfet();

 static Component* construct( QString type, QString id );
 static LibraryItem* libraryItem();

        void updateStep() override;

        void setPchannel( bool p ) override;
        void setDepletion( bool d ) override;

        void paint( QPainter* p, const QStyleOptionGraphicsItem* o, QWidget* w ) override;
};
