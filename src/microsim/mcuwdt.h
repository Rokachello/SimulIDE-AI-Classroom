/***************************************************************************
 *   Copyright (C) 2021 by Santiago González                               *
 *                                                                         *
 ***( see copyright.txt file at root folder )*******************************/

#pragma once

#include "mcuprescaled.h"
#include "e-element.h"

class eMcu;

class McuWdt : public McuPrescaled, public eElement
{
        friend class McuCreator;

    public:
        McuWdt( eMcu* mcu, QString name );
        ~McuWdt();

        bool enabled() { return m_wdtFuse; }
        void enable( bool en ) { m_wdtFuse = en; }

    protected:

        bool m_wdtFuse;
        bool m_ovfInter;
        bool m_ovfReset;

        uint64_t m_ovfPeriod; // overflow period in ps
        uint64_t m_clkPeriod; // clock period in ps
};
