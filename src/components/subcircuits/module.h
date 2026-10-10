/***************************************************************************
 *   Copyright (C) 2022 by Santiago González                               *
 *                                                                         *
 ***( see copyright.txt file at root folder )*******************************/

#pragma once

#include "shield.h"

class ModuleSubc : public ShieldSubc
{
    public:
        ModuleSubc( QString type, QString id, QString device );
        ~ModuleSubc();
        
        double zVal() { return zValue(); }
        void setZVal( double v);

        virtual void slotAttach() override;

    protected:
        virtual void renameTunnels() override;
};
